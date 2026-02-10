"""Tests for DownloadWorker."""

from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from internetarchive.bulk.disk import DiskPool
from internetarchive.workers.download import DownloadWorker


def _mock_session():
    """Create a mock ArchiveSession."""
    session = MagicMock()
    session.config = {}
    session.config_file = None
    return session


def _mock_item(
    identifier="test-item",
    is_dark=False,
    metadata=None,
    item_size=1024,
    download_errors=None,
):
    """Create a mock Item."""
    item = MagicMock()
    item.identifier = identifier
    item.is_dark = is_dark
    item.metadata = metadata if metadata is not None else {"title": "Test"}
    item.item_size = item_size
    item.download.return_value = download_errors or []
    return item


class TestDownloadWorker:
    def test_successful_download(self):
        session = _mock_session()
        item = _mock_item()
        session.get_item.return_value = item

        worker = DownloadWorker(session)
        # Patch per-thread session to return our mock
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is True
        assert result.identifier == "test-item"
        item.download.assert_called_once()

    def test_dark_item(self):
        session = _mock_session()
        item = _mock_item(is_dark=True)
        session.get_item.return_value = item

        worker = DownloadWorker(session)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("dark-item", {}, Event())
        assert result.success is False
        assert result.error == "item is dark"
        assert result.retry is False

    def test_nonexistent_item(self):
        session = _mock_session()
        item = _mock_item(metadata={})
        session.get_item.return_value = item

        worker = DownloadWorker(session)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("no-item", {}, Event())
        assert result.success is False
        assert result.error == "item does not exist"
        assert result.retry is False

    def test_download_with_errors(self):
        session = _mock_session()
        item = _mock_item(download_errors=["file1.txt", "file2.txt"])
        session.get_item.return_value = item

        worker = DownloadWorker(session)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is False
        assert "2 file(s) failed" in result.error
        assert result.retry is True

    def test_cancelled_before_start(self):
        session = _mock_session()
        worker = DownloadWorker(session)

        cancel = Event()
        cancel.set()

        result = worker.execute("test-item", {}, cancel)
        assert result.success is False
        assert result.error == "cancelled"
        assert result.retry is False

    def test_get_item_exception(self):
        session = _mock_session()
        session.get_item.side_effect = Exception("network error")

        worker = DownloadWorker(session)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("fail-item", {}, Event())
        assert result.success is False
        assert "network error" in result.error
        assert result.retry is True

    def test_download_exception(self):
        session = _mock_session()
        item = _mock_item()
        item.download.side_effect = Exception("write error")
        session.get_item.return_value = item

        worker = DownloadWorker(session)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is False
        assert "write error" in result.error
        assert result.retry is True

    def test_with_destdir(self):
        session = _mock_session()
        item = _mock_item()
        session.get_item.return_value = item

        worker = DownloadWorker(session, destdir="/mnt/data")
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is True
        call_kwargs = item.download.call_args[1]
        assert call_kwargs["destdir"] == "/mnt/data"

    def test_with_download_kwargs(self):
        session = _mock_session()
        item = _mock_item()
        session.get_item.return_value = item

        worker = DownloadWorker(
            session, glob_pattern="*.txt", checksum=True
        )
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is True
        call_kwargs = item.download.call_args[1]
        assert call_kwargs["glob_pattern"] == "*.txt"
        assert call_kwargs["checksum"] is True

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_with_disk_pool(self, mock_usage, tmp_path):
        mock_usage.return_value = MagicMock(
            total=100e9, used=50e9, free=50e9
        )

        session = _mock_session()
        item = _mock_item()
        session.get_item.return_value = item

        pool = DiskPool([str(tmp_path)])
        worker = DownloadWorker(session, disk_pool=pool)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is True
        call_kwargs = item.download.call_args[1]
        assert call_kwargs["destdir"] == str(tmp_path)

    def test_disk_pool_full_triggers_backoff(self):
        session = _mock_session()
        pool = MagicMock()
        pool.route.return_value = None

        worker = DownloadWorker(session, disk_pool=pool)
        worker._local = MagicMock()  # noqa: SLF001
        worker._local.session = session  # noqa: SLF001

        result = worker.execute("test-item", {}, Event())
        assert result.success is False
        assert result.backoff is True
        assert "all disks full" in result.error
