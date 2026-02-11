"""Tests for UIEvent, UIHandler, PlainUI, and ProgressBarUI."""

import io

import pytest

from internetarchive.bulk.ui import (
    _ARROW,
    _BOLD,
    _DIM,
    _RESET,
    _SYM_ACTIVE,
    _SYM_DONE,
    _SYM_FAIL,
    PlainUI,
    ProgressBarUI,
    UIEvent,
    UIHandler,
    _format_bytes,
    _truncate,
    _visible_len,
)


class TestUIEvent:
    def test_defaults(self):
        e = UIEvent(kind="job_started")
        assert e.kind == "job_started"
        assert e.seq == 0
        assert e.total == 0
        assert e.identifier == ""
        assert e.extra == {}

    def test_with_values(self):
        e = UIEvent(
            kind="job_completed",
            seq=5,
            total=100,
            identifier="foo",
            extra={"bytes": 1024},
            elapsed=3.5,
        )
        assert e.seq == 5
        assert e.extra["bytes"] == 1024


class TestUIHandler:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            UIHandler()


class TestPlainUI:
    def _capture(self):
        buf = io.StringIO()
        return buf, PlainUI(file=buf)

    def test_job_started(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1,
            total=100,
            identifier="foo-item",
            worker=2,
        ))
        output = buf.getvalue()
        assert "foo-item: started" in output
        assert "(worker" not in output
        assert "[1/100]" in output

    def test_job_completed_with_bytes(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_completed",
            seq=1,
            total=100,
            identifier="foo-item",
            extra={"bytes": 10_485_760},
            elapsed=44,
        ))
        output = buf.getvalue()
        assert "foo-item: completed" in output
        assert "10.0 MB" in output
        assert "44s" in output

    def test_job_completed_no_extra(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_completed",
            seq=1,
            total=100,
            identifier="foo-item",
        ))
        output = buf.getvalue()
        assert "foo-item: completed" in output

    def test_job_failed(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_failed",
            seq=2,
            total=100,
            identifier="bar-item",
            error="HTTP 503",
            retry=1,
            max_retries=3,
        ))
        output = buf.getvalue()
        assert "bar-item: failed: HTTP 503" in output
        assert "(retry 1/3)" in output

    def test_job_skipped(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_skipped",
            seq=1,
            total=100,
            identifier="done-item",
        ))
        output = buf.getvalue()
        assert "done-item: skipped (already completed)" in output

    def test_backoff_start(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="backoff_start",
            error="all disks full, waiting for in-flight jobs",
        ))
        output = buf.getvalue()
        assert "backoff:" in output
        assert "all disks full" in output

    def test_backoff_end(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(kind="backoff_end"))
        output = buf.getvalue()
        assert "backoff: resuming" in output

    def test_progress(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="progress",
            extra={"completed": 50, "failed": 2, "pending": 48},
        ))
        output = buf.getvalue()
        assert "50 completed" in output
        assert "2 failed" in output
        assert "48 pending" in output

    def test_timestamp_in_output(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(kind="job_started", seq=1, total=1,
                          identifier="x"))
        output = buf.getvalue()
        # Should contain timestamp like [HH:MM:SS]
        assert output.startswith("[")
        assert "]" in output


    def test_job_routed(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_routed",
            seq=1,
            total=100,
            identifier="foo-item",
            worker=0,
            extra={"destdir": "/mnt/disk1"},
        ))
        output = buf.getvalue()
        assert "foo-item:" in output
        assert _ARROW in output
        assert "/mnt/disk1" in output

    def test_shutdown(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(kind="shutdown"))
        output = buf.getvalue()
        assert "shutting down gracefully" in output


class TestVisibleLen:
    def test_plain_text(self):
        assert _visible_len("hello") == 5

    def test_ansi_not_counted(self):
        assert _visible_len(f"{_BOLD}hello{_RESET}") == 5

    def test_multiple_ansi(self):
        text = f"{_DIM}foo{_RESET} {_BOLD}bar{_RESET}"
        assert _visible_len(text) == 7

    def test_empty(self):
        assert _visible_len("") == 0

    def test_only_ansi(self):
        assert _visible_len(f"{_BOLD}{_RESET}") == 0


class TestTruncate:
    def test_no_truncation_needed(self):
        assert _truncate("short", 10) == "short"

    def test_plain_truncation(self):
        result = _truncate("hello world", 6)
        assert result == "hello\u2026"
        assert _visible_len(result) == 6

    def test_ansi_not_counted_toward_width(self):
        text = f"{_BOLD}hello world{_RESET}"
        result = _truncate(text, 6)
        # Should fit 5 visible chars + ellipsis = 6
        assert _visible_len(result) == 6
        # Should contain RESET before ellipsis (to close BOLD)
        assert _RESET in result

    def test_no_reset_when_no_ansi(self):
        result = _truncate("hello world", 6)
        assert _RESET not in result

    def test_width_one(self):
        result = _truncate("hello", 1)
        assert result == "\u2026"

    def test_empty_string(self):
        assert _truncate("", 10) == ""

    def test_exact_width(self):
        assert _truncate("hello", 5) == "hello"


class TestFormatBytes:
    def test_bytes(self):
        assert _format_bytes(500) == "500 B"
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1024 * 1024) == "1.0 MB"
        assert _format_bytes(1024 * 1024 * 1024) == "1.0 GB"


class TestProgressBarUI:
    """Tests for the two-bar-per-worker ProgressBarUI."""

    def _make_ui(self, max_workers=2):
        """Create a ProgressBarUI with a non-tty file stream.

        Returns (ui, file) where file is a StringIO.
        """
        f = io.StringIO()
        ui = ProgressBarUI(
            total=10, max_workers=max_workers, file=f
        )
        return ui, f

    def test_two_bars_created_per_worker(self):
        ui, _ = self._make_ui(max_workers=2)
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="item-a",
            worker=0,
        ))
        ui.handle(UIEvent(
            kind="job_started",
            seq=2, total=10,
            identifier="item-b",
            worker=1,
        ))
        assert 0 in ui._header_bars  # noqa: SLF001
        assert 0 in ui._progress_bars  # noqa: SLF001
        assert 1 in ui._header_bars  # noqa: SLF001
        assert 1 in ui._progress_bars  # noqa: SLF001
        ui.close()

    def test_job_started_sets_header_and_progress(self):
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="test-item",
            worker=0,
        ))
        hbar = ui._header_bars[0]  # noqa: SLF001
        # Header should contain the active symbol and
        # identifier (no ANSI since StringIO is not a tty).
        assert _SYM_ACTIVE in hbar.desc
        assert "test-item" in hbar.desc
        ui.close()

    def test_job_routed_updates_header_with_destdir(self):
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="test-item",
            worker=0,
        ))
        ui.handle(UIEvent(
            kind="job_routed",
            identifier="test-item",
            worker=0,
            extra={"destdir": "/mnt/disk1"},
        ))
        hbar = ui._header_bars[0]  # noqa: SLF001
        assert "/mnt/disk1" in hbar.desc
        assert _ARROW in hbar.desc
        # Worker state should be updated
        assert ui._worker_state[0]["destdir"] == "/mnt/disk1"  # noqa: SLF001
        ui.close()

    def test_job_completed_shows_done_symbol(self):
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="done-item",
            worker=0,
        ))
        ui.handle(UIEvent(
            kind="job_routed",
            identifier="done-item",
            worker=0,
            extra={"destdir": "/mnt/disk2"},
        ))
        ui.handle(UIEvent(
            kind="job_completed",
            seq=1, total=10,
            identifier="done-item",
            worker=0,
            extra={"item_size": 1024},
        ))
        hbar = ui._header_bars[0]  # noqa: SLF001
        assert _SYM_DONE in hbar.desc
        assert "/mnt/disk2" in hbar.desc
        ui.close()

    def test_job_failed_shows_fail_symbol(self):
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="fail-item",
            worker=0,
        ))
        ui.handle(UIEvent(
            kind="job_routed",
            identifier="fail-item",
            worker=0,
            extra={"destdir": "/mnt/disk1"},
        ))
        ui.handle(UIEvent(
            kind="job_failed",
            seq=1, total=10,
            identifier="fail-item",
            worker=0,
            error="item is dark",
        ))
        hbar = ui._header_bars[0]  # noqa: SLF001
        assert _SYM_FAIL in hbar.desc
        assert "/mnt/disk1" in hbar.desc
        ui.close()

    def test_file_started_updates_progress_bar(self):
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="item-a",
            worker=0,
        ))
        ui.handle(UIEvent(
            kind="file_started",
            identifier="item-a",
            worker=0,
            extra={"file_name": "data.zip", "file_size": 5000},
        ))
        pbar = ui._progress_bars[0]  # noqa: SLF001
        assert "data.zip" in pbar.desc
        # Reset should be pending
        assert 0 in ui._pending_reset  # noqa: SLF001
        ui.close()

    def test_shutdown_changes_overall_desc(self):
        ui, _ = self._make_ui()
        # Ensure overall bar exists
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="x",
            worker=0,
        ))
        ui.handle(UIEvent(kind="shutdown"))
        # tqdm.set_description appends ": " to desc
        assert "Shutting down..." in ui._overall_bar.desc  # noqa: SLF001
        ui.close()

    def test_close_clears_all_bars(self):
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="x",
            worker=0,
        ))
        assert len(ui._header_bars) == 1  # noqa: SLF001
        assert len(ui._progress_bars) == 1  # noqa: SLF001
        ui.close()
        assert len(ui._header_bars) == 0  # noqa: SLF001
        assert len(ui._progress_bars) == 0  # noqa: SLF001
        assert ui._overall_bar is None  # noqa: SLF001

    def test_no_ansi_on_non_tty(self):
        """StringIO is not a tty — ANSI codes should be absent."""
        ui, _ = self._make_ui()
        assert ui._use_color is False  # noqa: SLF001
        result = ui._ansi("\033[1m", "text")  # noqa: SLF001
        assert "\033[" not in result
        assert result == "text"
        ui.close()

    def test_no_w_prefix_in_descriptions(self):
        """Worker bars should not have W{idx} prefixes."""
        ui, _ = self._make_ui()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1, total=10,
            identifier="item-a",
            worker=0,
        ))
        hbar = ui._header_bars[0]  # noqa: SLF001
        pbar = ui._progress_bars[0]  # noqa: SLF001
        assert not hbar.desc.startswith("W0")
        assert not pbar.desc.startswith("W0")
        ui.close()
