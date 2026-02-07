from __future__ import annotations

import io

from internetarchive.bulk.ui.base import UIEvent
from internetarchive.bulk.ui.plain import PlainUI, _format_bytes


class TestUIEvent:
    """Tests for UIEvent dataclass."""

    def test_required_fields(self):
        event = UIEvent(kind="item_started", identifier="test-item", worker=0)
        assert event.kind == "item_started"
        assert event.identifier == "test-item"
        assert event.worker == 0

    def test_default_optional_fields(self):
        event = UIEvent(kind="item_started", identifier="test-item", worker=0)
        assert event.item_index is None
        assert event.filename is None
        assert event.bytes_done is None
        assert event.bytes_total is None
        assert event.elapsed is None
        assert event.files_ok is None
        assert event.error is None

    def test_all_fields(self):
        event = UIEvent(
            kind="file_progress",
            identifier="test-item",
            worker=2,
            item_index=5,
            filename="data.zip",
            bytes_done=1024,
            bytes_total=4096,
            elapsed=1.5,
            files_ok=3,
            error="partial timeout",
        )
        assert event.kind == "file_progress"
        assert event.identifier == "test-item"
        assert event.worker == 2
        assert event.item_index == 5
        assert event.filename == "data.zip"
        assert event.bytes_done == 1024
        assert event.bytes_total == 4096
        assert event.elapsed == 1.5
        assert event.files_ok == 3
        assert event.error == "partial timeout"


class TestPlainUI:
    """Tests for PlainUI plain-text output."""

    @staticmethod
    def _make_ui(
        total_items: int | None = 10,
        num_workers: int = 1,
    ) -> tuple[PlainUI, io.StringIO]:
        stream = io.StringIO()
        ui = PlainUI(stream=stream, total_items=total_items, num_workers=num_workers)
        return ui, stream

    # -- item_started --

    def test_item_started(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="item_started",
            identifier="my-item",
            worker=0,
            item_index=1,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "my-item" in output
        assert "1/10" in output
        assert "started" in output.lower()

    def test_item_started_no_total(self):
        ui, stream = self._make_ui(total_items=None)
        event = UIEvent(
            kind="item_started",
            identifier="my-item",
            worker=0,
            item_index=3,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "my-item" in output
        assert "3" in output

    # -- item_completed --

    def test_item_completed(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="item_completed",
            identifier="done-item",
            worker=0,
            item_index=2,
            bytes_done=2048,
            files_ok=5,
            elapsed=3.21,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "done-item" in output
        assert "2/10" in output

    # -- item_failed --

    def test_item_failed(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="item_failed",
            identifier="broken-item",
            worker=0,
            item_index=4,
            error="Connection refused",
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "broken-item" in output
        assert "Connection refused" in output

    # -- item_skipped --

    def test_item_skipped(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="item_skipped",
            identifier="skip-item",
            worker=0,
            item_index=6,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "skip-item" in output
        assert "skip" in output.lower()

    # -- file_progress --

    def test_file_progress(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="file_progress",
            identifier="prog-item",
            worker=0,
            filename="big_file.tar",
            bytes_done=512,
            bytes_total=1024,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "prog-item" in output
        assert "big_file.tar" in output

    # -- disk_update --

    def test_disk_update(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="disk_update",
            identifier="disk-item",
            worker=0,
            bytes_done=1_000_000,
            bytes_total=2_000_000,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        assert "disk-item" in output

    # -- unknown event kind --

    def test_unknown_event_no_crash(self):
        """An unrecognized event kind should not crash."""
        ui, _stream = self._make_ui()
        event = UIEvent(
            kind="totally_unknown",
            identifier="mystery",
            worker=0,
        )
        ui.handle_event(event)
        # Just verify it doesn't raise; output is optional.

    # -- timestamp format --

    def test_output_has_timestamp(self):
        ui, stream = self._make_ui()
        event = UIEvent(
            kind="item_started",
            identifier="ts-item",
            worker=0,
            item_index=1,
        )
        ui.handle_event(event)
        output = stream.getvalue()
        # Expect [HH:MM:SS] at the start
        assert output.startswith("[")
        assert "]" in output

    # -- print_summary --

    def test_print_summary(self):
        ui, stream = self._make_ui()
        ui.print_summary(
            completed=8,
            failed=1,
            skipped=1,
            total_bytes=1_073_741_824,
            elapsed=120.0,
        )
        output = stream.getvalue()
        assert "8" in output
        assert "1" in output

    def test_print_summary_zero(self):
        ui, stream = self._make_ui()
        ui.print_summary(
            completed=0,
            failed=0,
            skipped=0,
            total_bytes=0,
            elapsed=0.0,
        )
        output = stream.getvalue()
        assert "0" in output


class TestFormatBytes:
    """Tests for the _format_bytes helper."""

    def test_bytes(self):
        assert _format_bytes(0) == "0 B"
        assert _format_bytes(1) == "1 B"
        assert _format_bytes(999) == "999 B"

    def test_kilobytes(self):
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1536) == "1.5 KB"

    def test_megabytes(self):
        result = _format_bytes(1_048_576)
        assert "MB" in result
        assert result.startswith("1.0")

    def test_gigabytes(self):
        result = _format_bytes(1_073_741_824)
        assert "GB" in result
        assert result.startswith("1.0")

    def test_terabytes(self):
        result = _format_bytes(1_099_511_627_776)
        assert "TB" in result
        assert result.startswith("1.0")

    def test_large_terabytes(self):
        result = _format_bytes(5_497_558_138_880)
        assert "TB" in result
        assert result.startswith("5.0")
