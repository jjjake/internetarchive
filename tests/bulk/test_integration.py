#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.

"""
tests.bulk.test_integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Full round-trip integration tests for the bulk download pipeline.

Exercises BulkEngine + DownloadWorker + JobLog + DiskPool + PlainUI
together with mocked HTTP via the ``responses`` library.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import io
import json
import re
from unittest.mock import patch

import responses

from internetarchive import get_session
from internetarchive.bulk.disk import DiskPool
from internetarchive.bulk.engine import BulkEngine
from internetarchive.bulk.jobs import JobLog
from internetarchive.bulk.ui.plain import PlainUI
from internetarchive.workers.download import DownloadWorker

# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

IDENTIFIERS = ["item-1", "item-2", "item-3"]

LAST_MOD_HEADER = {
    "Last-Modified": "Tue, 14 Nov 2023 20:25:48 GMT",
}


class FakeStatvfs:
    """Minimal os.statvfs result with controllable free space."""

    def __init__(
        self, free_bytes: int, block_size: int = 4096
    ):
        self.f_frsize = block_size
        self.f_bavail = free_bytes // block_size


def _make_metadata(identifier: str) -> dict:
    """Build a minimal metadata dict for one item."""
    return {
        "metadata": {"identifier": identifier},
        "item_size": 100,
        "files_count": 1,
        "files": [
            {
                "name": "test.txt",
                "source": "original",
                "size": "17",
                "md5": "abc",
                "format": "Text",
            },
        ],
    }


def _register_mocks(identifiers: list[str]) -> None:
    """Register responses mocks for metadata and file downloads."""
    for ident in identifiers:
        meta = _make_metadata(ident)
        responses.add(
            responses.GET,
            f"https://archive.org/metadata/{ident}",
            json=meta,
        )

    # A single regex-matched response for all file downloads.
    # In responses 0.23.x the last registered response for a
    # given URL is reused indefinitely.
    responses.add(
        responses.GET,
        re.compile(r"https://archive\.org/download/.*"),
        body=b"test content here",
        adding_headers=LAST_MOD_HEADER,
    )


def _session_factory():
    """Return a fresh ArchiveSession with dummy credentials."""
    return get_session(
        config={"s3": {"access": "t", "secret": "t"}},
    )


def _make_disk_pool(destdir: str):
    """Create a DiskPool backed by *destdir* with mocked statvfs.

    Returns a (pool, patcher) tuple.  The caller must manage the
    patcher's lifecycle or use it inside a ``with`` block.
    """
    free = 100 * 1024**3  # 100 GiB
    fake = FakeStatvfs(free)
    patcher = patch(
        "os.statvfs", return_value=fake,
    )
    patcher.start()
    pool = DiskPool([destdir], margin=0)
    return pool, patcher


# -----------------------------------------------------------------
# Tests
# -----------------------------------------------------------------


@responses.activate
def test_full_round_trip(tmp_path):
    """Download 3 items with 2 workers, verify joblog."""
    _register_mocks(IDENTIFIERS)

    log_file = tmp_path / "jobs.jsonl"
    jl = JobLog(str(log_file))
    pool, patcher = _make_disk_pool(str(tmp_path))

    try:
        stream = io.StringIO()
        ui = PlainUI(
            stream=stream,
            total_items=3,
            num_workers=2,
        )
        worker = DownloadWorker(
            session_factory=_session_factory,
            download_kwargs={
                "ignore_existing": True,
                "verbose": False,
            },
        )
        engine = BulkEngine(
            worker=worker,
            job_log=jl,
            disk_pool=pool,
            num_workers=2,
            job_retries=0,
            op="download",
            ui_handler=ui.handle_event,
        )
        results = engine.run(IDENTIFIERS)
    finally:
        patcher.stop()

    jl.close()

    assert results["completed"] == 3
    assert results["failed"] == 0

    # Verify joblog has completed entries for all items.
    lines = log_file.read_text().strip().split("\n")
    events = [json.loads(line) for line in lines]
    completed = [
        e for e in events if e["event"] == "completed"
    ]
    assert len(completed) == 3

    completed_ids = sorted(e["id"] for e in completed)
    assert completed_ids == sorted(IDENTIFIERS)

    # Verify files were written to disk.
    for ident in IDENTIFIERS:
        item_dir = tmp_path / ident
        assert item_dir.is_dir(), (
            f"expected directory for {ident}"
        )
        assert (item_dir / "test.txt").exists()

    # Verify resume: re-running should skip all items.
    jl2 = JobLog(str(log_file))
    for ident in IDENTIFIERS:
        assert jl2.should_skip(ident), (
            f"{ident} should be skipped on resume"
        )
    jl2.close()


@responses.activate
def test_resume_skips_completed_items(tmp_path):
    """Pre-populate joblog with completed items, re-run, verify
    they are all skipped."""
    _register_mocks(IDENTIFIERS)

    log_file = tmp_path / "jobs.jsonl"

    # --- First run: complete all 3 items. ---
    jl1 = JobLog(str(log_file))
    pool, patcher = _make_disk_pool(str(tmp_path))

    try:
        worker = DownloadWorker(
            session_factory=_session_factory,
            download_kwargs={
                "ignore_existing": True,
                "verbose": False,
            },
        )
        engine = BulkEngine(
            worker=worker,
            job_log=jl1,
            disk_pool=pool,
            num_workers=2,
            job_retries=0,
            op="download",
            ui_handler=None,
        )
        first_results = engine.run(IDENTIFIERS)
    finally:
        patcher.stop()

    jl1.close()
    assert first_results["completed"] == 3

    # --- Second run: same identifiers, same log file. ---
    jl2 = JobLog(str(log_file))
    pool2, patcher2 = _make_disk_pool(str(tmp_path))

    try:
        worker2 = DownloadWorker(
            session_factory=_session_factory,
            download_kwargs={
                "ignore_existing": True,
                "verbose": False,
            },
        )
        engine2 = BulkEngine(
            worker=worker2,
            job_log=jl2,
            disk_pool=pool2,
            num_workers=2,
            job_retries=0,
            op="download",
            ui_handler=None,
        )
        second_results = engine2.run(IDENTIFIERS)
    finally:
        patcher2.stop()

    jl2.close()

    assert second_results["skipped"] == 3
    assert second_results["completed"] == 0
    assert second_results["failed"] == 0


@responses.activate
def test_single_worker_mode(tmp_path):
    """Run with max_workers=1 to verify serial execution works."""
    _register_mocks(IDENTIFIERS)

    log_file = tmp_path / "jobs.jsonl"
    jl = JobLog(str(log_file))
    pool, patcher = _make_disk_pool(str(tmp_path))

    try:
        stream = io.StringIO()
        ui = PlainUI(
            stream=stream,
            total_items=3,
            num_workers=1,
        )
        worker = DownloadWorker(
            session_factory=_session_factory,
            download_kwargs={
                "ignore_existing": True,
                "verbose": False,
            },
        )
        engine = BulkEngine(
            worker=worker,
            job_log=jl,
            disk_pool=pool,
            num_workers=1,
            job_retries=0,
            op="download",
            ui_handler=ui.handle_event,
        )
        results = engine.run(IDENTIFIERS)
    finally:
        patcher.stop()

    jl.close()

    assert results["completed"] == 3
    assert results["failed"] == 0
    assert results["skipped"] == 0

    # Verify joblog entries.
    lines = log_file.read_text().strip().split("\n")
    events = [json.loads(line) for line in lines]
    completed = [
        e for e in events if e["event"] == "completed"
    ]
    assert len(completed) == 3

    # Verify files on disk.
    for ident in IDENTIFIERS:
        assert (tmp_path / ident / "test.txt").exists()

    # Verify UI output was produced.
    output = stream.getvalue()
    for ident in IDENTIFIERS:
        assert ident in output
