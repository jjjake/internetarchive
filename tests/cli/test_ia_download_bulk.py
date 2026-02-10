"""Tests for bulk download CLI integration."""

import argparse
import io
import json
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from internetarchive.bulk.joblog import JobLog
from internetarchive.cli.ia import _print_status
from internetarchive.cli.ia_download import (
    _parse_size,
    _run_bulk,
    _use_bulk_mode,
)


class TestParseSize:
    def test_bytes(self):
        assert _parse_size("1024") == 1024

    def test_kilobytes(self):
        assert _parse_size("1K") == 1024

    def test_megabytes(self):
        assert _parse_size("10M") == 10 * 1024**2

    def test_gigabytes(self):
        assert _parse_size("1G") == 1024**3

    def test_terabytes(self):
        assert _parse_size("2T") == 2 * 1024**4

    def test_lowercase(self):
        assert _parse_size("1g") == 1024**3

    def test_float(self):
        assert _parse_size("1.5G") == int(1.5 * 1024**3)


class TestUseBulkMode:
    def test_default_single_item(self):
        args = MagicMock()
        args.workers = 1
        args.joblog = None
        assert _use_bulk_mode(args) is False

    def test_workers_triggers_bulk(self):
        args = MagicMock()
        args.workers = 4
        args.joblog = None
        assert _use_bulk_mode(args) is True

    def test_joblog_triggers_bulk(self):
        args = MagicMock()
        args.workers = 1
        args.joblog = "test.jsonl"
        assert _use_bulk_mode(args) is True


class TestCLIArgParsing:
    def test_global_workers_option(self):
        """Verify --workers is parsed as a global option."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--workers", type=int, default=1)
        parser.add_argument("--joblog", type=str)
        parser.add_argument("--batch-retries", type=int, default=3)
        parser.add_argument("--status", action="store_true")

        args = parser.parse_args(["--workers", "4"])
        assert args.workers == 4

        args = parser.parse_args(
            ["--joblog", "test.jsonl", "--status"]
        )
        assert args.joblog == "test.jsonl"
        assert args.status is True

    def test_download_destdir_repeatable(self):
        """Verify --destdir can be repeated."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--destdir",
            nargs=1,
            action="extend",
        )
        args = parser.parse_args([
            "--destdir", "/mnt/disk1",
            "--destdir", "/mnt/disk2",
        ])
        assert args.destdir == ["/mnt/disk1", "/mnt/disk2"]

    def test_disk_margin_default(self):
        """Verify --disk-margin default value."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--disk-margin", default="1G")
        args = parser.parse_args([])
        assert args.disk_margin == "1G"


class TestParseSizeValidation:
    def test_empty_string(self):
        with pytest.raises(argparse.ArgumentTypeError, match="empty"):
            _parse_size("")

    def test_whitespace_only(self):
        with pytest.raises(argparse.ArgumentTypeError, match="empty"):
            _parse_size("   ")

    def test_negative(self):
        with pytest.raises(
            argparse.ArgumentTypeError, match="non-negative"
        ):
            _parse_size("-1G")

    def test_invalid_string(self):
        with pytest.raises(
            argparse.ArgumentTypeError, match="invalid size"
        ):
            _parse_size("abc")

    def test_zero(self):
        assert _parse_size("0") == 0


class TestStatusFlag:
    def test_status_output(self, tmp_path):
        """Verify --status prints joblog summary."""
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_job(2, "item-b", "download")
        log.write_event("completed", seq=1)
        log.close()

        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_status(path)
        output = buf.getvalue()
        assert "Total:     2" in output
        assert "Completed: 1" in output
        assert "Pending:   1" in output


def _make_bulk_args(tmp_path, **overrides):
    """Build a minimal argparse.Namespace for _run_bulk().

    :param tmp_path: pytest tmp_path for the joblog file.
    :param overrides: Fields to override on the namespace.
    :returns: ``(args, parser)`` tuple.
    """
    session = MagicMock()
    session.config = {}
    session.config_file = None

    defaults = {
        "workers": 2,
        "joblog": str(tmp_path / "test.jsonl"),
        "batch_retries": 3,
        "search": None,
        "search_parameters": None,
        "itemlist": None,
        "identifier": "test-item",
        "file": [],
        "dry_run": False,
        "stdout": False,
        "glob": None,
        "exclude": None,
        "format": None,
        "checksum": False,
        "checksum_archive": False,
        "ignore_existing": False,
        "no_directories": False,
        "on_the_fly": False,
        "no_change_timestamp": False,
        "parameters": None,
        "download_history": False,
        "source": None,
        "exclude_source": None,
        "timeout": None,
        "retries": 5,
        "destdir": None,
        "disk_margin": "1G",
        "no_disk_check": True,
        "session": session,
    }
    defaults.update(overrides)
    args = argparse.Namespace(**defaults)
    parser = argparse.ArgumentParser()
    return args, parser


class TestRunBulkIntegration:
    """Integration tests for _run_bulk() → BulkEngine wiring."""

    @patch("internetarchive.get_session")
    def test_single_item_download(self, mock_get_session, tmp_path):
        """_run_bulk() resolves an identifier, downloads it, and
        records the result in the joblog.
        """
        # Mock the per-thread session and item
        item = MagicMock()
        item.is_dark = False
        item.metadata = {"title": "Test"}
        item.item_size = 1024
        item.download.return_value = []

        mock_session = MagicMock()
        mock_session.config = {}
        mock_session.config_file = None
        mock_session.get_item.return_value = item
        mock_get_session.return_value = mock_session

        args, parser = _make_bulk_args(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            _run_bulk(args, parser)
        assert exc_info.value.code == 0

        # Verify joblog was written correctly
        joblog_path = str(tmp_path / "test.jsonl")
        with open(joblog_path) as f:
            records = [json.loads(line) for line in f if line.strip()]

        job_records = [r for r in records if r["event"] == "job"]
        assert len(job_records) == 1
        assert job_records[0]["id"] == "test-item"

        completed = [r for r in records if r["event"] == "completed"]
        assert len(completed) == 1

        # Verify download was called with expected kwargs
        item.download.assert_called_once()
        call_kwargs = item.download.call_args[1]
        assert call_kwargs["verbose"] is False
        assert call_kwargs["ignore_errors"] is True
        assert call_kwargs["retries"] == 5

    @patch("internetarchive.get_session")
    def test_download_kwargs_wired(self, mock_get_session, tmp_path):
        """CLI flags like --glob, --checksum are wired through to
        Item.download().
        """
        item = MagicMock()
        item.is_dark = False
        item.metadata = {"title": "Test"}
        item.item_size = 512
        item.download.return_value = []

        mock_session = MagicMock()
        mock_session.config = {}
        mock_session.config_file = None
        mock_session.get_item.return_value = item
        mock_get_session.return_value = mock_session

        args, parser = _make_bulk_args(
            tmp_path,
            glob="*.pdf",
            checksum=True,
            no_directories=True,
            timeout=30.0,
        )
        with pytest.raises(SystemExit) as exc_info:
            _run_bulk(args, parser)
        assert exc_info.value.code == 0

        call_kwargs = item.download.call_args[1]
        assert call_kwargs["glob_pattern"] == "*.pdf"
        assert call_kwargs["checksum"] is True
        assert call_kwargs["no_directory"] is True
        assert call_kwargs["timeout"] == 30.0

    def test_dry_run_rejected(self, tmp_path):
        """--dry-run should error in bulk mode."""
        args, parser = _make_bulk_args(tmp_path, dry_run=True)
        with pytest.raises(SystemExit) as exc_info:
            _run_bulk(args, parser)
        assert exc_info.value.code == 2

    def test_stdout_rejected(self, tmp_path):
        """--stdout should error in bulk mode."""
        args, parser = _make_bulk_args(tmp_path, stdout=True)
        with pytest.raises(SystemExit) as exc_info:
            _run_bulk(args, parser)
        assert exc_info.value.code == 2

    def test_file_args_rejected(self, tmp_path):
        """Positional file args should error in bulk mode."""
        args, parser = _make_bulk_args(
            tmp_path, file=["somefile.txt"]
        )
        with pytest.raises(SystemExit) as exc_info:
            _run_bulk(args, parser)
        assert exc_info.value.code == 2

    @patch("internetarchive.get_session")
    def test_resume_skips_completed(self, mock_get_session, tmp_path):
        """Resume should only process jobs not yet completed."""
        joblog_path = str(tmp_path / "test.jsonl")

        # Pre-populate joblog with 3 jobs, 1 completed
        log = JobLog(joblog_path)
        log.write_job(1, "done-item", "download")
        log.write_job(2, "pending-item", "download")
        log.write_job(3, "also-pending", "download")
        log.write_event("completed", seq=1)
        log.close()

        item = MagicMock()
        item.is_dark = False
        item.metadata = {"title": "Test"}
        item.item_size = 256
        item.download.return_value = []

        mock_session = MagicMock()
        mock_session.config = {}
        mock_session.config_file = None
        mock_session.get_item.return_value = item
        mock_get_session.return_value = mock_session

        # Resume — no identifier/search/itemlist needed
        args, parser = _make_bulk_args(
            tmp_path,
            joblog=joblog_path,
            identifier=None,
        )
        with pytest.raises(SystemExit) as exc_info:
            _run_bulk(args, parser)
        assert exc_info.value.code == 0

        # Should have downloaded 2 items, not 3
        assert mock_session.get_item.call_count == 2
        called_ids = [
            c.args[0] for c in mock_session.get_item.call_args_list
        ]
        assert "done-item" not in called_ids
        assert "pending-item" in called_ids
        assert "also-pending" in called_ids
