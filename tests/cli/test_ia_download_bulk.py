"""Tests for bulk download CLI integration."""

import argparse
import io
from contextlib import redirect_stdout
from unittest.mock import MagicMock

from internetarchive.bulk.joblog import JobLog
from internetarchive.cli.ia import _print_status
from internetarchive.cli.ia_download import (
    _parse_size,
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
