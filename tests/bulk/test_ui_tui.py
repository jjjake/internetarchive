from __future__ import annotations

from internetarchive.bulk.ui.base import UIEvent
from internetarchive.bulk.ui.tui import TUIState


class TestTUIStateInit:
    """Tests for TUIState initialization."""

    def test_defaults(self):
        state = TUIState(num_workers=4, total_items=100)
        assert state.num_workers == 4
        assert state.total_items == 100
        assert state.completed == 0
        assert state.failed == 0
        assert state.skipped == 0
        assert state.total_bytes == 0
        assert state.active_workers == {}
        assert len(state.recent) == 0

    def test_total_items_none(self):
        state = TUIState(num_workers=2)
        assert state.total_items is None


class TestTUIStateTracksWorkers:
    """Tests for item_started event handling."""

    def test_tui_state_tracks_workers(self):
        state = TUIState(num_workers=4, total_items=100)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="nasa-001",
            worker=1,
            item_index=1,
            bytes_total=1024,
        ))
        assert 1 in state.active_workers
        assert state.active_workers[1]["identifier"] == "nasa-001"
        assert state.active_workers[1]["item_index"] == 1
        assert state.active_workers[1]["bytes_total"] == 1024
        assert state.active_workers[1]["bytes_done"] == 0
        assert state.active_workers[1]["filename"] is None

    def test_multiple_workers(self):
        state = TUIState(num_workers=4, total_items=100)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="nasa-001",
            worker=0,
            item_index=1,
        ))
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="nasa-002",
            worker=1,
            item_index=2,
        ))
        assert len(state.active_workers) == 2
        assert state.active_workers[0]["identifier"] == "nasa-001"
        assert state.active_workers[1]["identifier"] == "nasa-002"

    def test_worker_replaced_on_new_start(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="old-item",
            worker=0,
            item_index=1,
        ))
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="new-item",
            worker=0,
            item_index=2,
        ))
        assert state.active_workers[0]["identifier"] == "new-item"


class TestTUIStateCompletesItem:
    """Tests for item_completed event handling."""

    def test_tui_state_completes_item(self):
        state = TUIState(num_workers=4, total_items=100)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="nasa-001",
            worker=1,
            item_index=1,
        ))
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="nasa-001",
            worker=1,
            bytes_total=1024,
        ))
        assert state.completed == 1
        assert 1 not in state.active_workers

    def test_completed_adds_to_recent(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="item-1",
            worker=0,
            bytes_total=2048,
            elapsed=5.0,
            files_ok=3,
        ))
        assert len(state.recent) == 1
        entry = state.recent[0]
        assert entry["identifier"] == "item-1"
        assert entry["status"] == "completed"
        assert entry["bytes_total"] == 2048
        assert entry["elapsed"] == 5.0
        assert entry["files_ok"] == 3

    def test_completed_accumulates_total_bytes(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="i1",
            worker=0,
            bytes_total=100,
        ))
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="i2",
            worker=0,
            bytes_total=200,
        ))
        assert state.total_bytes == 300
        assert state.completed == 2

    def test_completed_no_bytes_total(self):
        """Completing with bytes_total=None should not crash."""
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="i1",
            worker=0,
        ))
        assert state.completed == 1
        assert state.total_bytes == 0


class TestTUIStateFailedItem:
    """Tests for item_failed event handling."""

    def test_tui_state_failed_item(self):
        state = TUIState(num_workers=4, total_items=100)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="broken",
            worker=2,
            item_index=5,
        ))
        state.handle_event(UIEvent(
            kind="item_failed",
            identifier="broken",
            worker=2,
            error="Connection refused",
        ))
        assert state.failed == 1
        assert 2 not in state.active_workers

    def test_failed_adds_to_recent(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_failed",
            identifier="bad-item",
            worker=0,
            error="timeout",
        ))
        assert len(state.recent) == 1
        entry = state.recent[0]
        assert entry["identifier"] == "bad-item"
        assert entry["status"] == "failed"
        assert entry["error"] == "timeout"

    def test_failed_no_error_message(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_failed",
            identifier="bad-item",
            worker=0,
        ))
        assert state.failed == 1
        entry = state.recent[0]
        assert entry["error"] is None


class TestTUIStateSkippedItem:
    """Tests for item_skipped event handling."""

    def test_tui_state_skipped_item(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_skipped",
            identifier="skip-me",
            worker=0,
        ))
        assert state.skipped == 1

    def test_skipped_adds_to_recent(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_skipped",
            identifier="skip-me",
            worker=0,
        ))
        assert len(state.recent) == 1
        entry = state.recent[0]
        assert entry["identifier"] == "skip-me"
        assert entry["status"] == "skipped"

    def test_skipped_does_not_increment_completed(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_skipped",
            identifier="skip-me",
            worker=0,
        ))
        assert state.completed == 0
        assert state.failed == 0


class TestTUIStateTracksRecent:
    """Tests for the recent deque."""

    def test_tui_state_tracks_recent(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="i1",
            worker=0,
            bytes_total=100,
        ))
        state.handle_event(UIEvent(
            kind="item_failed",
            identifier="i2",
            worker=1,
            error="timeout",
        ))
        assert len(state.recent) == 2
        assert state.recent[0]["status"] == "completed"
        assert state.recent[1]["status"] == "failed"

    def test_tui_state_recent_maxlen(self):
        """Recent deque should cap at 10 entries."""
        state = TUIState(num_workers=2, total_items=20)
        for i in range(15):
            state.handle_event(UIEvent(
                kind="item_completed",
                identifier=f"item-{i}",
                worker=0,
                bytes_total=100,
            ))
        assert len(state.recent) == 10
        # Oldest entries (0-4) should be evicted.
        ids = [e["identifier"] for e in state.recent]
        assert ids[0] == "item-5"
        assert ids[-1] == "item-14"

    def test_recent_mixed_statuses(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="c1",
            worker=0,
            bytes_total=100,
        ))
        state.handle_event(UIEvent(
            kind="item_failed",
            identifier="f1",
            worker=1,
            error="err",
        ))
        state.handle_event(UIEvent(
            kind="item_skipped",
            identifier="s1",
            worker=0,
        ))
        statuses = [e["status"] for e in state.recent]
        assert statuses == ["completed", "failed", "skipped"]


class TestTUIStateFileProgress:
    """Tests for file_progress event handling."""

    def test_tui_state_file_progress(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="nasa-001",
            worker=0,
            item_index=1,
        ))
        state.handle_event(UIEvent(
            kind="file_progress",
            identifier="nasa-001",
            worker=0,
            filename="photo.jpg",
            bytes_done=512,
            bytes_total=1024,
        ))
        w = state.active_workers[0]
        assert w["filename"] == "photo.jpg"
        assert w["bytes_done"] == 512
        assert w["bytes_total"] == 1024

    def test_file_progress_updates_in_place(self):
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="nasa-001",
            worker=0,
            item_index=1,
        ))
        state.handle_event(UIEvent(
            kind="file_progress",
            identifier="nasa-001",
            worker=0,
            filename="photo.jpg",
            bytes_done=256,
            bytes_total=1024,
        ))
        state.handle_event(UIEvent(
            kind="file_progress",
            identifier="nasa-001",
            worker=0,
            filename="photo.jpg",
            bytes_done=768,
            bytes_total=1024,
        ))
        w = state.active_workers[0]
        assert w["bytes_done"] == 768

    def test_file_progress_unknown_worker_ignored(self):
        """Progress for a worker not in active_workers is ignored."""
        state = TUIState(num_workers=2, total_items=10)
        # No item_started for worker 3.
        state.handle_event(UIEvent(
            kind="file_progress",
            identifier="mystery",
            worker=3,
            filename="file.bin",
            bytes_done=100,
            bytes_total=200,
        ))
        assert 3 not in state.active_workers

    def test_file_progress_none_bytes(self):
        """Progress with None bytes should default to 0."""
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="test",
            worker=0,
            item_index=1,
        ))
        state.handle_event(UIEvent(
            kind="file_progress",
            identifier="test",
            worker=0,
            filename="data.bin",
            bytes_done=None,
            bytes_total=None,
        ))
        w = state.active_workers[0]
        assert w["bytes_done"] == 0
        assert w["bytes_total"] == 0


class TestTUIStateUnknownEvent:
    """Tests for unknown event kinds."""

    def test_tui_state_unknown_event(self):
        """An unrecognized event kind should not crash."""
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="totally_unknown",
            identifier="mystery",
            worker=0,
        ))
        # State should be unchanged.
        assert state.completed == 0
        assert state.failed == 0
        assert state.skipped == 0
        assert len(state.active_workers) == 0
        assert len(state.recent) == 0

    def test_disk_update_event_ignored(self):
        """disk_update is not handled by TUIState."""
        state = TUIState(num_workers=2, total_items=10)
        state.handle_event(UIEvent(
            kind="disk_update",
            identifier="disk",
            worker=0,
            bytes_done=500,
            bytes_total=1000,
        ))
        assert state.completed == 0


class TestTUIStateFullWorkflow:
    """End-to-end workflow test for TUIState."""

    def test_full_workflow(self):
        state = TUIState(num_workers=2, total_items=5)

        # Worker 0 starts item 1.
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="item-001",
            worker=0,
            item_index=1,
            bytes_total=2048,
        ))
        assert len(state.active_workers) == 1

        # Worker 1 starts item 2.
        state.handle_event(UIEvent(
            kind="item_started",
            identifier="item-002",
            worker=1,
            item_index=2,
            bytes_total=4096,
        ))
        assert len(state.active_workers) == 2

        # File progress on worker 0.
        state.handle_event(UIEvent(
            kind="file_progress",
            identifier="item-001",
            worker=0,
            filename="readme.txt",
            bytes_done=1024,
            bytes_total=2048,
        ))
        assert state.active_workers[0]["filename"] == "readme.txt"
        assert state.active_workers[0]["bytes_done"] == 1024

        # Worker 0 completes.
        state.handle_event(UIEvent(
            kind="item_completed",
            identifier="item-001",
            worker=0,
            bytes_total=2048,
            elapsed=3.5,
            files_ok=1,
        ))
        assert state.completed == 1
        assert state.total_bytes == 2048
        assert 0 not in state.active_workers

        # Worker 1 fails.
        state.handle_event(UIEvent(
            kind="item_failed",
            identifier="item-002",
            worker=1,
            error="500 Internal Server Error",
        ))
        assert state.failed == 1
        assert 1 not in state.active_workers

        # Item 3 is skipped.
        state.handle_event(UIEvent(
            kind="item_skipped",
            identifier="item-003",
            worker=0,
        ))
        assert state.skipped == 1

        # Check recent history.
        assert len(state.recent) == 3
        statuses = [e["status"] for e in state.recent]
        assert statuses == ["completed", "failed", "skipped"]

        # Verify final counts.
        assert state.completed == 1
        assert state.failed == 1
        assert state.skipped == 1
        assert state.total_bytes == 2048
