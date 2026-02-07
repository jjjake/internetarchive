from __future__ import annotations

import pytest

rich = pytest.importorskip("rich")

from internetarchive.bulk.ui.base import UIEvent
from internetarchive.bulk.ui.rich_tui import RichTUI


class TestRichTUICreation:
    """Tests for RichTUI instantiation."""

    def test_creates_with_defaults(self):
        tui = RichTUI(num_workers=4, total_items=100)
        assert tui is not None
        assert tui._state.num_workers == 4
        assert tui._state.total_items == 100

    def test_creates_without_total(self):
        tui = RichTUI(num_workers=2)
        assert tui._state.total_items is None

    def test_live_not_started_initially(self):
        tui = RichTUI(num_workers=2, total_items=10)
        assert tui._live is None


class TestRichTUIHandlesEvents:
    """Tests for event handling via RichTUI."""

    def test_item_started(self):
        tui = RichTUI(num_workers=4, total_items=100)
        tui.handle_event(UIEvent(
            kind="item_started",
            identifier="test",
            worker=0,
            item_index=1,
        ))
        assert 0 in tui._state.active_workers
        w = tui._state.active_workers[0]
        assert w["identifier"] == "test"

    def test_item_completed(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="item_started",
            identifier="done-item",
            worker=0,
            item_index=1,
        ))
        tui.handle_event(UIEvent(
            kind="item_completed",
            identifier="done-item",
            worker=0,
            bytes_total=2048,
            elapsed=1.5,
            files_ok=3,
        ))
        assert tui._state.completed == 1
        assert 0 not in tui._state.active_workers

    def test_item_failed(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="item_failed",
            identifier="bad-item",
            worker=0,
            error="connection refused",
        ))
        assert tui._state.failed == 1

    def test_item_skipped(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="item_skipped",
            identifier="skip-me",
            worker=0,
        ))
        assert tui._state.skipped == 1

    def test_file_progress(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="item_started",
            identifier="prog-item",
            worker=0,
            item_index=1,
        ))
        tui.handle_event(UIEvent(
            kind="file_progress",
            identifier="prog-item",
            worker=0,
            filename="data.bin",
            bytes_done=512,
            bytes_total=1024,
        ))
        w = tui._state.active_workers[0]
        assert w["filename"] == "data.bin"
        assert w["bytes_done"] == 512

    def test_unknown_event_no_crash(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="totally_unknown",
            identifier="mystery",
            worker=0,
        ))
        assert tui._state.completed == 0


class TestRichTUIRendering:
    """Tests for the _render() method output."""

    def test_render_returns_table(self):
        from rich.table import Table

        tui = RichTUI(num_workers=2, total_items=10)
        result = tui._render()
        assert isinstance(result, Table)

    def test_render_idle_workers(self):
        """Rendering with idle workers should not crash."""
        tui = RichTUI(num_workers=3, total_items=5)
        table = tui._render()
        # 1 summary + 3 workers = 4 rows minimum.
        assert table.row_count >= 4

    def test_render_active_worker(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="item_started",
            identifier="active-item",
            worker=0,
            item_index=1,
            bytes_total=2048,
        ))
        tui.handle_event(UIEvent(
            kind="file_progress",
            identifier="active-item",
            worker=0,
            filename="photo.jpg",
            bytes_done=1024,
            bytes_total=2048,
        ))
        table = tui._render()
        assert table.row_count >= 2

    def test_render_with_recent(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.handle_event(UIEvent(
            kind="item_completed",
            identifier="done-1",
            worker=0,
            bytes_total=1024,
        ))
        tui.handle_event(UIEvent(
            kind="item_failed",
            identifier="fail-1",
            worker=1,
            error="timeout",
        ))
        table = tui._render()
        # summary + 2 workers + blank + "Recent:" + 2 entries
        assert table.row_count >= 7

    def test_render_long_filename_truncated(self):
        """Filenames longer than 20 chars are truncated."""
        tui = RichTUI(num_workers=1, total_items=5)
        tui.handle_event(UIEvent(
            kind="item_started",
            identifier="trunc",
            worker=0,
            item_index=1,
        ))
        long_name = "a" * 30
        tui.handle_event(UIEvent(
            kind="file_progress",
            identifier="trunc",
            worker=0,
            filename=long_name,
            bytes_done=100,
            bytes_total=200,
        ))
        # Just verify no crash; the truncation is
        # handled inside _render_worker.
        table = tui._render()
        assert table.row_count >= 1


class TestRichTUILifecycle:
    """Tests for start/stop lifecycle."""

    def test_start_stop(self):
        tui = RichTUI(num_workers=2, total_items=10)
        tui.start()
        assert tui._live is not None
        tui.stop()
        assert tui._live is None

    def test_stop_without_start(self):
        """Stopping without starting should not crash."""
        tui = RichTUI(num_workers=2, total_items=10)
        tui.stop()
        assert tui._live is None

    def test_handle_event_while_live(self):
        """Events during live display should update."""
        tui = RichTUI(num_workers=2, total_items=10)
        tui.start()
        try:
            tui.handle_event(UIEvent(
                kind="item_started",
                identifier="live-item",
                worker=0,
                item_index=1,
            ))
            assert tui._state.active_workers[0][
                "identifier"
            ] == "live-item"
        finally:
            tui.stop()


class TestRichTUIRenderHelpers:
    """Tests for static render helper methods."""

    def test_render_summary_with_total(self):
        from internetarchive.bulk.ui.tui import TUIState

        state = TUIState(num_workers=2, total_items=50)
        state.completed = 10
        state.failed = 2
        state.skipped = 3
        state.total_bytes = 1024
        text = RichTUI._render_summary(state)
        plain = text.plain
        # done = completed + failed + skipped = 15
        assert "15/50" in plain
        assert "Failed: 2" in plain
        assert "Skipped: 3" in plain
        assert "Elapsed:" in plain

    def test_render_summary_without_total(self):
        from internetarchive.bulk.ui.tui import TUIState

        state = TUIState(num_workers=2)
        state.completed = 5
        text = RichTUI._render_summary(state)
        assert "Completed: 5" in text.plain

    def test_render_worker_idle(self):
        from internetarchive.bulk.ui.tui import TUIState

        state = TUIState(num_workers=2, total_items=10)
        text = RichTUI._render_worker(state, 0)
        assert "idle" in text.plain

    def test_render_worker_active(self):
        from internetarchive.bulk.ui.tui import TUIState

        state = TUIState(num_workers=2, total_items=10)
        state.active_workers[0] = {
            "identifier": "my-item",
            "item_index": 1,
            "bytes_total": 2048,
            "bytes_done": 1024,
            "filename": "file.txt",
            "started_at": None,
        }
        text = RichTUI._render_worker(state, 0)
        plain = text.plain
        assert "my-item" in plain
        assert "2.0 KB" in plain

    def test_render_worker_no_total_bytes(self):
        from internetarchive.bulk.ui.tui import TUIState

        state = TUIState(num_workers=1, total_items=5)
        state.active_workers[0] = {
            "identifier": "item",
            "item_index": 1,
            "bytes_total": 0,
            "bytes_done": 512,
            "filename": None,
        }
        text = RichTUI._render_worker(state, 0)
        assert "item" in text.plain

    def test_render_recent_completed(self):
        entry = {
            "identifier": "done-1",
            "status": "completed",
            "bytes_total": 4096,
        }
        text = RichTUI._render_recent(entry)
        plain = text.plain
        assert "+" in plain
        assert "done-1" in plain
        assert "KB" in plain

    def test_render_recent_failed(self):
        entry = {
            "identifier": "bad-1",
            "status": "failed",
            "error": "timeout",
        }
        text = RichTUI._render_recent(entry)
        plain = text.plain
        assert "X" in plain
        assert "bad-1" in plain
        assert "timeout" in plain

    def test_render_recent_skipped(self):
        entry = {
            "identifier": "skip-1",
            "status": "skipped",
        }
        text = RichTUI._render_recent(entry)
        plain = text.plain
        assert "o" in plain
        assert "skip-1" in plain

    def test_render_recent_unknown_status(self):
        entry = {
            "identifier": "weird",
            "status": "exploded",
        }
        text = RichTUI._render_recent(entry)
        assert "?" in text.plain
