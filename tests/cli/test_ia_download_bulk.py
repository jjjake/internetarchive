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

"""Tests for bulk download CLI arguments and commands."""
from __future__ import annotations

import argparse
import json

import pytest

from internetarchive.bulk.commands import (
    _build_download_kwargs,
    _get_identifiers,
    _select_ui,
    bulk_status,
)
from internetarchive.bulk.ui.plain import PlainUI
from internetarchive.cli.ia_download import setup


def _make_parser():
    """Create a parser with the download subcommand registered."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    setup(subparsers)
    return parser


class TestBulkCLIArgs:
    """Test that bulk-specific arguments are registered."""

    def test_workers_default(self):
        parser = _make_parser()
        args = parser.parse_args(["download", "test-id"])
        assert args.workers == 1

    def test_workers_flag(self):
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--workers", "4", "test-id"]
        )
        assert args.workers == 4

    def test_workers_short_flag(self):
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "-w", "8", "test-id"]
        )
        assert args.workers == 8

    def test_joblog_flag(self, tmp_path):
        log_path = str(tmp_path / "test.jsonl")
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--joblog", log_path, "test-id"]
        )
        assert args.joblog == log_path

    def test_joblog_default_none(self):
        parser = _make_parser()
        args = parser.parse_args(["download", "test-id"])
        assert args.joblog is None

    def test_destdirs_single(self, tmp_path):
        d = str(tmp_path)
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "test-id", "--destdirs", d]
        )
        assert args.destdirs == [d]

    def test_destdirs_multiple(self, tmp_path):
        d1 = str(tmp_path / "a")
        d2 = str(tmp_path / "b")
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "test-id", "--destdirs", d1, d2]
        )
        assert args.destdirs == [d1, d2]

    def test_destdirs_default_none(self):
        parser = _make_parser()
        args = parser.parse_args(["download", "test-id"])
        assert args.destdirs is None

    def test_disk_margin_default(self):
        parser = _make_parser()
        args = parser.parse_args(["download", "test-id"])
        assert args.disk_margin == "1G"

    def test_disk_margin_custom(self):
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--disk-margin", "500M", "test-id"]
        )
        assert args.disk_margin == "500M"

    def test_no_disk_check_default(self):
        parser = _make_parser()
        args = parser.parse_args(["download", "test-id"])
        assert args.no_disk_check is False

    def test_no_disk_check_flag(self):
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--no-disk-check", "test-id"]
        )
        assert args.no_disk_check is True

    def test_status_flag(self, tmp_path):
        log_path = str(tmp_path / "test.jsonl")
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--status", "--joblog", log_path]
        )
        assert args.status is True

    def test_verify_flag(self, tmp_path):
        log_path = str(tmp_path / "test.jsonl")
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--verify", "--joblog", log_path]
        )
        assert args.verify is True

    def test_status_without_identifier(self, tmp_path):
        """--status should not require an identifier."""
        log_path = str(tmp_path / "test.jsonl")
        parser = _make_parser()
        # Should not raise.
        args = parser.parse_args(
            ["download", "--status", "--joblog", log_path]
        )
        assert args.status is True
        assert args.identifier is None

    def test_verify_without_identifier(self, tmp_path):
        """--verify should not require an identifier."""
        log_path = str(tmp_path / "test.jsonl")
        parser = _make_parser()
        # Should not raise.
        args = parser.parse_args(
            ["download", "--verify", "--joblog", log_path]
        )
        assert args.verify is True
        assert args.identifier is None


class TestBulkStatus:
    """Test bulk_status prints summary from a job log."""

    def test_status_empty_log(self, tmp_path, capsys):
        log_path = str(tmp_path / "test.jsonl")
        # Create empty log file.
        with open(log_path, "w"):
            pass

        # An empty log has 0 completed, 0 failed, 0 skipped.
        bulk_status(log_path)
        captured = capsys.readouterr()
        assert "completed: 0" in captured.out
        assert "failed:    0" in captured.out
        assert "skipped:   0" in captured.out

    def test_status_with_completed_items(
        self, tmp_path, capsys
    ):
        log_path = str(tmp_path / "test.jsonl")
        records = [
            {
                "id": "item1",
                "event": "completed",
                "op": "download",
                "ts": "2024-01-01T00:00:00+00:00",
                "destdir": str(tmp_path),
                "bytes_transferred": 1024,
                "files_ok": 5,
                "files_skipped": 0,
                "files_failed": 0,
                "elapsed": 10.0,
            },
            {
                "id": "item2",
                "event": "failed",
                "op": "download",
                "ts": "2024-01-01T00:00:01+00:00",
                "error": "network error",
                "retries_left": 0,
            },
        ]
        with open(log_path, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

        bulk_status(log_path)
        captured = capsys.readouterr()
        assert "completed: 1" in captured.out
        assert "failed:    1" in captured.out
        assert "skipped:   0" in captured.out
        assert "item2: network error" in captured.out

    def test_status_file_not_found(self):
        with pytest.raises(SystemExit) as exc_info:
            bulk_status("/nonexistent/path.jsonl")
        assert exc_info.value.code == 1


class TestBulkCommands:
    """Test helper functions in bulk.commands."""

    def test_build_download_kwargs_defaults(self):
        args = argparse.Namespace(
            glob=None,
            exclude=None,
            format=None,
            source=None,
            exclude_source=None,
            dry_run=False,
            quiet=False,
            ignore_existing=False,
            checksum=False,
            checksum_archive=False,
            no_directories=False,
            retries=5,
            on_the_fly=False,
            no_change_timestamp=False,
            download_history=False,
            stdout=False,
            parameters=None,
            timeout=None,
        )
        kwargs = _build_download_kwargs(args)
        assert kwargs["verbose"] is True
        assert kwargs["retries"] == 5
        assert kwargs["ignore_history_dir"] is True
        assert kwargs["dry_run"] is False
        assert "params" not in kwargs
        assert "timeout" not in kwargs
        assert "glob_pattern" not in kwargs

    def test_build_download_kwargs_with_options(self):
        args = argparse.Namespace(
            glob="*.pdf",
            exclude="*thumb*",
            format=["PDF", "EPUB"],
            source=["original"],
            exclude_source=["derivative"],
            dry_run=True,
            quiet=True,
            ignore_existing=True,
            checksum=True,
            checksum_archive=True,
            no_directories=True,
            retries=10,
            on_the_fly=True,
            no_change_timestamp=True,
            download_history=True,
            stdout=True,
            parameters={"cnt": "0"},
            timeout=30.0,
        )
        kwargs = _build_download_kwargs(args)
        assert kwargs["glob_pattern"] == "*.pdf"
        assert kwargs["exclude_pattern"] == "*thumb*"
        assert kwargs["formats"] == ["PDF", "EPUB"]
        assert kwargs["source"] == ["original"]
        assert kwargs["exclude_source"] == ["derivative"]
        assert kwargs["dry_run"] is True
        assert kwargs["verbose"] is False
        assert kwargs["ignore_existing"] is True
        assert kwargs["checksum"] is True
        assert kwargs["checksum_archive"] is True
        assert kwargs["no_directory"] is True
        assert kwargs["retries"] == 10
        assert kwargs["on_the_fly"] is True
        assert kwargs["no_change_timestamp"] is True
        assert kwargs["ignore_history_dir"] is False
        assert kwargs["stdout"] is True
        assert kwargs["params"] == {"cnt": "0"}
        assert kwargs["timeout"] == 30.0

    def test_get_identifiers_from_itemlist(self, tmp_path):
        itemlist = tmp_path / "items.txt"
        itemlist.write_text("item1\nitem2\n  item3  \n\n")

        fh = open(str(itemlist))
        args = argparse.Namespace(
            itemlist=fh,
            search=None,
            identifier=None,
        )
        ids, total = _get_identifiers(args)
        fh.close()
        assert ids == ["item1", "item2", "item3"]
        assert total == 3

    def test_get_identifiers_empty_itemlist(self, tmp_path):
        itemlist = tmp_path / "empty.txt"
        itemlist.write_text("\n\n  \n")

        fh = open(str(itemlist))
        args = argparse.Namespace(
            itemlist=fh,
            search=None,
            identifier=None,
        )
        ids, total = _get_identifiers(args)
        fh.close()
        assert ids == []
        assert total == 0


class TestSelectUI:
    """Test _select_ui TUI resolution logic."""

    def test_no_ui_flag_returns_plain(self):
        args = argparse.Namespace(no_ui=True, ui=False)
        ui = _select_ui(args, 4, 100)
        assert isinstance(ui, PlainUI)

    def test_no_flags_non_tty_returns_plain(self, monkeypatch):
        args = argparse.Namespace(no_ui=False, ui=False)
        monkeypatch.setattr("sys.stderr", type("F", (), {
            "isatty": lambda self: False,
            "write": lambda self, s: None,
            "flush": lambda self: None,
        })())
        ui = _select_ui(args, 4, 100)
        assert isinstance(ui, PlainUI)

    def test_ui_flag_tries_rich_then_curses(self, monkeypatch):
        args = argparse.Namespace(no_ui=False, ui=True)
        ui = _select_ui(args, 2, 50)
        # Should return either RichTUI, CursesTUI, or PlainUI
        # depending on what's available. Just verify it succeeds.
        assert hasattr(ui, "handle_event")

    def test_ui_flag_args_parsed(self):
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--ui", "test-id"]
        )
        assert args.ui is True

    def test_no_ui_flag_args_parsed(self):
        parser = _make_parser()
        args = parser.parse_args(
            ["download", "--no-ui", "test-id"]
        )
        assert args.no_ui is True
