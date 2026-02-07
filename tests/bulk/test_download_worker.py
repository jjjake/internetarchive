from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import responses

from internetarchive import get_session
from internetarchive.bulk.worker import VerifyResult, WorkerResult
from internetarchive.utils import json
from internetarchive.workers.download import DownloadWorker

PROTOCOL = "https:"
DOWNLOAD_URL_RE = re.compile(
    rf"{PROTOCOL}//archive.org/download/.*"
)
METADATA_URL_RE = re.compile(
    rf"{PROTOCOL}//archive.org/metadata/.*"
)
EXPECTED_LAST_MOD_HEADER = {
    "Last-Modified": "Tue, 14 Nov 2023 20:25:48 GMT",
}

NASA_METADATA = {
    "metadata": {"identifier": "nasa"},
    "item_size": 12345,
    "files_count": 2,
    "files": [
        {
            "name": "nasa_meta.xml",
            "source": "metadata",
            "size": "100",
            "md5": "abc123",
            "format": "Metadata",
        },
        {
            "name": "photo.jpg",
            "source": "original",
            "size": "12245",
            "md5": "def456",
            "format": "JPEG",
        },
    ],
}


def _mock_session_factory(item):
    """Return a factory that yields a mock session whose
    get_item() always returns *item*."""
    def factory():
        session = MagicMock()
        session.get_item.return_value = item
        return session
    return factory


# ---------------------------------------------------------
# TestDownloadWorkerEstimateSize
# ---------------------------------------------------------


class TestDownloadWorkerEstimateSize:
    """Tests for DownloadWorker.estimate_size()."""

    def test_estimate_from_item_size(self):
        item = MagicMock()
        item.item_size = "524288000"

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.estimate_size("test-item")
        assert result == 524288000

    def test_estimate_returns_none_for_missing(self):
        item = MagicMock()
        item.item_size = None

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.estimate_size("test-item")
        assert result is None

    def test_estimate_returns_none_on_exception(self):
        """If get_item raises, estimate_size returns None."""
        def bad_factory():
            session = MagicMock()
            session.get_item.side_effect = Exception("boom")
            return session

        worker = DownloadWorker(
            session_factory=bad_factory,
            download_kwargs={},
        )
        result = worker.estimate_size("test-item")
        assert result is None


# ---------------------------------------------------------
# TestDownloadWorkerExecute
# ---------------------------------------------------------


class TestDownloadWorkerExecute:
    """Tests for DownloadWorker.execute()."""

    @responses.activate
    def test_successful_download(self, tmp_path):
        """Full integration: mock HTTP, create a real session,
        verify WorkerResult.success is True."""
        responses.add(
            responses.GET,
            METADATA_URL_RE,
            json=NASA_METADATA,
            content_type="application/json",
        )
        # Register enough download responses for both files.
        for _ in range(2):
            responses.add(
                responses.GET,
                DOWNLOAD_URL_RE,
                body="test content",
                adding_headers=EXPECTED_LAST_MOD_HEADER,
            )

        session = get_session(
            config={"s3": {"access": "test", "secret": "test"}},
        )
        worker = DownloadWorker(
            session_factory=lambda: session,
            download_kwargs={},
        )
        result = worker.execute("nasa", tmp_path)

        assert isinstance(result, WorkerResult)
        assert result.success is True
        assert result.identifier == "nasa"
        assert result.files_failed == 0
        assert result.error is None

        # Files should exist on disk.
        item_dir = tmp_path / "nasa"
        assert item_dir.is_dir()
        assert (item_dir / "nasa_meta.xml").exists()
        assert (item_dir / "photo.jpg").exists()

    def test_dark_item_returns_failure(self, tmp_path):
        """A dark item should produce a failed WorkerResult."""
        item = MagicMock()
        item.is_dark = True
        item.identifier = "dark-item"

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.execute("dark-item", tmp_path)

        assert isinstance(result, WorkerResult)
        assert result.success is False
        assert "dark" in result.error

    def test_execute_handles_get_item_exception(self, tmp_path):
        """If get_item raises, execute returns a failure."""
        def bad_factory():
            session = MagicMock()
            session.get_item.side_effect = Exception("offline")
            return session

        worker = DownloadWorker(
            session_factory=bad_factory,
            download_kwargs={},
        )
        result = worker.execute("broken", tmp_path)

        assert result.success is False
        assert "offline" in result.error

    def test_execute_accepts_path_object(self, tmp_path):
        """destdir can be a Path object."""
        item = MagicMock()
        item.is_dark = False
        item.files = []
        item.download.return_value = []

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.execute("test-item", Path(tmp_path))

        assert result.success is True
        # Ensure str(destdir) was passed to item.download
        item.download.assert_called_once()
        call_kwargs = item.download.call_args[1]
        assert isinstance(call_kwargs["destdir"], str)


# ---------------------------------------------------------
# TestDownloadWorkerVerify
# ---------------------------------------------------------


class TestDownloadWorkerVerify:
    """Tests for DownloadWorker.verify()."""

    def test_verify_existing_item(self, tmp_path):
        """All files present on disk => complete=True."""
        item = MagicMock()
        item.files = [
            {"name": "file_a.txt"},
            {"name": "file_b.txt"},
        ]

        # Create the files on disk.
        item_dir = tmp_path / "test-item"
        item_dir.mkdir()
        (item_dir / "file_a.txt").write_text("aaa")
        (item_dir / "file_b.txt").write_text("bbb")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("test-item", tmp_path)

        assert isinstance(result, VerifyResult)
        assert result.complete is True
        assert result.files_expected == 2
        assert result.files_found == 2
        assert result.files_missing == []

    def test_verify_missing_files(self, tmp_path):
        """Some files missing => complete=False."""
        item = MagicMock()
        item.files = [
            {"name": "present.txt"},
            {"name": "missing.txt"},
            {"name": "also_missing.txt"},
        ]

        # Only create one file on disk.
        item_dir = tmp_path / "test-item"
        item_dir.mkdir()
        (item_dir / "present.txt").write_text("ok")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("test-item", tmp_path)

        assert isinstance(result, VerifyResult)
        assert result.complete is False
        assert result.files_expected == 3
        assert result.files_found == 1
        assert set(result.files_missing) == {
            "missing.txt",
            "also_missing.txt",
        }

    def test_verify_empty_item(self, tmp_path):
        """An item with no files => complete=True, 0 expected."""
        item = MagicMock()
        item.files = []

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("empty-item", tmp_path)

        assert result.complete is True
        assert result.files_expected == 0
        assert result.files_found == 0

    def test_verify_handles_get_item_exception(self, tmp_path):
        """If get_item raises, verify returns incomplete."""
        def bad_factory():
            session = MagicMock()
            session.get_item.side_effect = Exception("gone")
            return session

        worker = DownloadWorker(
            session_factory=bad_factory,
            download_kwargs={},
        )
        result = worker.verify("gone-item", tmp_path)

        assert result.complete is False
        assert result.files_expected == 0
        assert result.files_found == 0

    def test_verify_accepts_string_destdir(self, tmp_path):
        """destdir can be a plain string."""
        item = MagicMock()
        item.files = [{"name": "readme.txt"}]

        item_dir = tmp_path / "str-item"
        item_dir.mkdir()
        (item_dir / "readme.txt").write_text("hello")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("str-item", str(tmp_path))

        assert result.complete is True
        assert result.files_found == 1


# ---------------------------------------------------------
# TestDownloadWorkerSessionCaching
# ---------------------------------------------------------


class TestDownloadWorkerSessionCaching:
    """Tests for per-thread session caching."""

    def test_same_thread_reuses_session(self):
        """Calling _get_session() twice in the same thread
        returns the same object."""
        call_count = 0

        def counting_factory():
            nonlocal call_count
            call_count += 1
            return MagicMock()

        worker = DownloadWorker(
            session_factory=counting_factory,
            download_kwargs={},
        )
        s1 = worker._get_session()  # noqa: SLF001
        s2 = worker._get_session()  # noqa: SLF001

        assert s1 is s2
        assert call_count == 1

    def test_default_kwargs_empty(self):
        """When no download_kwargs given, _kwargs is empty."""
        worker = DownloadWorker(
            session_factory=MagicMock,
            download_kwargs=None,
        )
        assert worker._kwargs == {}  # noqa: SLF001
