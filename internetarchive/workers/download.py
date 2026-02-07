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
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.workers.download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Download worker for bulk operations.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import os
import threading
from logging import getLogger
from pathlib import Path
from typing import Callable

from internetarchive.bulk.worker import (
    BaseWorker,
    VerifyResult,
    WorkerResult,
)

log = getLogger(__name__)


class DownloadWorker(BaseWorker):
    """Downloads an item's files using Item.download().

    Each worker thread gets its own ArchiveSession via
    *session_factory* (``requests.Session`` is not thread-safe).
    """

    def __init__(
        self,
        session_factory: Callable,
        download_kwargs: dict | None = None,
    ) -> None:
        """
        Args:
            session_factory: Callable returning a new
                :class:`~internetarchive.ArchiveSession`.
                Called once per thread.
            download_kwargs: Keyword arguments passed through
                to :meth:`Item.download()
                <internetarchive.Item.download>`
                (e.g. ``glob_pattern``, ``formats``,
                ``retries``).
        """
        self._session_factory = session_factory
        self._kwargs: dict = dict(download_kwargs or {})
        self._sessions: dict[int | None, object] = {}
        self._lock = threading.Lock()

    # ----------------------------------------------------------
    # Per-thread session management
    # ----------------------------------------------------------

    def _get_session(self):
        """Return an ArchiveSession for the current thread.

        Sessions are cached by ``threading.current_thread().ident``
        so each thread reuses a single session instance.
        """
        tid = threading.current_thread().ident
        with self._lock:
            if tid not in self._sessions:
                self._sessions[tid] = self._session_factory()
            return self._sessions[tid]

    # ----------------------------------------------------------
    # BaseWorker interface
    # ----------------------------------------------------------

    def estimate_size(self, identifier: str) -> int | None:
        """Return the item's total size in bytes, or *None*.

        Uses the ``item_size`` field from the Archive.org
        metadata API.
        """
        session = self._get_session()
        try:
            item = session.get_item(identifier)
        except Exception:
            log.warning(
                "could not retrieve item %s for size estimate",
                identifier,
            )
            return None
        if item.item_size is None:
            return None
        try:
            return int(item.item_size)
        except (ValueError, TypeError):
            return None

    def execute(
        self,
        identifier: str,
        destdir: str | Path,
    ) -> WorkerResult:
        """Download all matching files for *identifier*.

        Delegates to :meth:`Item.download()
        <internetarchive.Item.download>`,
        passing *destdir* and any extra keyword arguments supplied
        at construction time.
        """
        session = self._get_session()
        try:
            item = session.get_item(identifier)
        except Exception as exc:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=str(exc),
            )

        if item.is_dark:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=f"item {identifier} is dark",
            )

        try:
            errors = item.download(
                destdir=str(destdir),
                **self._kwargs,
            )
        except Exception as exc:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=str(exc),
            )

        # item.download() returns a list of filenames that
        # failed.  An empty list means complete success.
        files_failed = len(errors) if errors else 0
        total_files = len(item.files) if item.files else 0
        files_ok = total_files - files_failed

        # Calculate bytes transferred by scanning the destdir.
        item_dir = os.path.join(str(destdir), identifier)
        bytes_transferred = _count_bytes(item_dir)

        return WorkerResult(
            success=(files_failed == 0),
            identifier=identifier,
            bytes_transferred=bytes_transferred,
            files_ok=files_ok,
            files_failed=files_failed,
            error=(
                f"{files_failed} file(s) failed"
                if files_failed
                else None
            ),
        )

    def verify(
        self,
        identifier: str,
        destdir: str | Path,
    ) -> VerifyResult:
        """Check downloaded files against the item's file list.

        Iterates over the item's metadata file list and checks
        that each file exists on disk under
        ``<destdir>/<identifier>/<name>``.
        """
        session = self._get_session()
        try:
            item = session.get_item(identifier)
        except Exception:
            return VerifyResult(
                identifier=identifier,
                complete=False,
                files_expected=0,
                files_found=0,
                files_missing=[],
            )

        expected_files = [
            f["name"]
            for f in (item.files or [])
            if "name" in f
        ]
        files_expected = len(expected_files)

        item_dir = Path(str(destdir)) / identifier
        files_missing: list[str] = []
        files_found = 0

        for name in expected_files:
            path = item_dir / name
            if path.exists():
                files_found += 1
            else:
                files_missing.append(name)

        return VerifyResult(
            identifier=identifier,
            complete=(files_found == files_expected),
            files_expected=files_expected,
            files_found=files_found,
            files_missing=files_missing,
        )


def _count_bytes(directory: str) -> int:
    """Walk *directory* and sum file sizes."""
    total = 0
    if not os.path.isdir(directory):
        return 0
    for dirpath, _dirnames, filenames in os.walk(directory):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                total += os.path.getsize(fpath)
            except OSError:
                pass
    return total
