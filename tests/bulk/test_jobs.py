from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from internetarchive.bulk.jobs import JobLog


class TestJobLogBasic:
    """Tests for basic JobLog logging operations."""

    def test_log_started(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "test-item",
            op="download",
            destdir="/data/downloads",
            est_bytes=1024,
            worker="w0",
            retry=0,
        )
        jl.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["id"] == "test-item"
        assert rec["event"] == "started"
        assert rec["op"] == "download"
        assert rec["destdir"] == "/data/downloads"
        assert rec["est_bytes"] == 1024
        assert rec["worker"] == "w0"
        assert rec["retry"] == 0
        assert "ts" in rec

    def test_log_completed(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_completed(
            "test-item",
            op="download",
            destdir="/data/downloads",
            bytes_transferred=2048,
            files_ok=5,
            files_skipped=1,
            files_failed=0,
            elapsed=3.14,
        )
        jl.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["id"] == "test-item"
        assert rec["event"] == "completed"
        assert rec["op"] == "download"
        assert rec["destdir"] == "/data/downloads"
        assert rec["bytes_transferred"] == 2048
        assert rec["files_ok"] == 5
        assert rec["files_skipped"] == 1
        assert rec["files_failed"] == 0
        assert rec["elapsed"] == 3.14

    def test_log_failed(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_failed(
            "bad-item",
            op="download",
            error="Connection refused",
            retries_left=2,
        )
        jl.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["id"] == "bad-item"
        assert rec["event"] == "failed"
        assert rec["op"] == "download"
        assert rec["error"] == "Connection refused"
        assert rec["retries_left"] == 2

    def test_log_skipped(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_skipped("dark-item", op="download", reason="dark")
        jl.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["id"] == "dark-item"
        assert rec["event"] == "skipped"
        assert rec["op"] == "download"
        assert rec["reason"] == "dark"

    def test_log_rerouted(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_rerouted(
            "big-item",
            op="download",
            from_destdir="/data/disk1",
            to_destdir="/data/disk2",
            reason="low_disk_space",
        )
        jl.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["id"] == "big-item"
        assert rec["event"] == "rerouted"
        assert rec["op"] == "download"
        assert rec["from_destdir"] == "/data/disk1"
        assert rec["to_destdir"] == "/data/disk2"
        assert rec["reason"] == "low_disk_space"

    def test_timestamp_is_iso8601_utc(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "ts-item", op="download", destdir="/d", est_bytes=0,
            worker="w0", retry=0,
        )
        jl.close()

        rec = json.loads(log_path.read_text().strip())
        ts = rec["ts"]
        # Must end with Z or +00:00 for UTC
        assert ts.endswith(("Z", "+00:00"))
        # Must parse as a valid ISO 8601 timestamp
        if ts.endswith("Z"):
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None

    def test_multiple_events_append(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "item-1", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=0,
        )
        jl.log_completed(
            "item-1", op="download", destdir="/d", bytes_transferred=100,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=1.0,
        )
        jl.log_started(
            "item-2", op="download", destdir="/d", est_bytes=200,
            worker="w1", retry=0,
        )
        jl.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["id"] == "item-1"
        assert json.loads(lines[0])["event"] == "started"
        assert json.loads(lines[1])["id"] == "item-1"
        assert json.loads(lines[1])["event"] == "completed"
        assert json.loads(lines[2])["id"] == "item-2"


class TestJobLogResumeSemantics:
    """Tests for should_skip() resume rules."""

    def test_completed_item_should_skip(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "done-item", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=0,
        )
        jl.log_completed(
            "done-item", op="download", destdir="/d", bytes_transferred=100,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=1.0,
        )
        assert jl.should_skip("done-item") is True

    def test_skipped_exists_should_skip(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_skipped("exists-item", op="download", reason="exists")
        assert jl.should_skip("exists-item") is True

    def test_skipped_dark_should_skip(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_skipped("dark-item", op="download", reason="dark")
        assert jl.should_skip("dark-item") is True

    def test_skipped_empty_should_skip(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_skipped("empty-item", op="download", reason="empty")
        assert jl.should_skip("empty-item") is True

    def test_skipped_no_disk_space_should_not_skip(self, tmp_path):
        """Disk space may free up — retry these items."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_skipped("disk-item", op="download", reason="no_disk_space")
        assert jl.should_skip("disk-item") is False

    def test_failed_should_not_skip(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_failed(
            "fail-item", op="download", error="Timeout", retries_left=2,
        )
        assert jl.should_skip("fail-item") is False

    def test_started_without_completion_should_not_skip(self, tmp_path):
        """Crash recovery — started but never completed should retry."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "crash-item", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=0,
        )
        assert jl.should_skip("crash-item") is False

    def test_unknown_item_should_not_skip(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        assert jl.should_skip("never-seen") is False

    def test_completed_then_started_again_should_skip(self, tmp_path):
        """Once completed, the item should always be skipped.

        Even if extra started events appear after completion, the
        completion event takes precedence.
        """
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_completed(
            "item-x", op="download", destdir="/d", bytes_transferred=100,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=1.0,
        )
        # A subsequent started event should NOT override completion
        jl.log_started(
            "item-x", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=1,
        )
        assert jl.should_skip("item-x") is True

    def test_failed_then_completed_should_skip(self, tmp_path):
        """A retry that completes after a failure should be skipped."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_failed(
            "retry-item", op="download", error="Timeout", retries_left=1,
        )
        assert jl.should_skip("retry-item") is False
        jl.log_completed(
            "retry-item", op="download", destdir="/d", bytes_transferred=100,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=2.0,
        )
        assert jl.should_skip("retry-item") is True


class TestJobLogResumeFromDisk:
    """Tests for resuming from an existing JSONL file on disk."""

    def test_resume_from_existing_file(self, tmp_path):
        """A new JobLog should load state from an existing file."""
        log_path = tmp_path / "job.jsonl"

        # First session: log some events
        jl1 = JobLog(log_path)
        jl1.log_completed(
            "done-item", op="download", destdir="/d", bytes_transferred=100,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=1.0,
        )
        jl1.log_failed(
            "fail-item", op="download", error="Timeout", retries_left=0,
        )
        jl1.close()

        # Second session: should restore state
        jl2 = JobLog(log_path)
        assert jl2.should_skip("done-item") is True
        assert jl2.should_skip("fail-item") is False
        assert jl2.should_skip("new-item") is False
        jl2.close()

    def test_resume_appends_to_existing(self, tmp_path):
        """New events should be appended, not overwrite existing content."""
        log_path = tmp_path / "job.jsonl"

        jl1 = JobLog(log_path)
        jl1.log_skipped("dark-item", op="download", reason="dark")
        jl1.close()

        jl2 = JobLog(log_path)
        jl2.log_completed(
            "new-item", op="download", destdir="/d", bytes_transferred=50,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=0.5,
        )
        jl2.close()

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == "dark-item"
        assert json.loads(lines[1])["id"] == "new-item"


class TestJobLogStatus:
    """Tests for status() summary statistics."""

    def test_empty_status(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        st = jl.status()
        assert st["completed"] == 0
        assert st["failed"] == 0
        assert st["skipped"] == 0
        assert st["total_bytes"] == 0
        assert st["total_files_ok"] == 0
        assert st["failed_items"] == []
        jl.close()

    def test_status_after_mixed_events(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)

        jl.log_completed(
            "item-1", op="download", destdir="/d", bytes_transferred=1000,
            files_ok=5, files_skipped=0, files_failed=0, elapsed=1.0,
        )
        jl.log_completed(
            "item-2", op="download", destdir="/d", bytes_transferred=2000,
            files_ok=3, files_skipped=1, files_failed=0, elapsed=2.0,
        )
        jl.log_failed(
            "item-3", op="download", error="404 Not Found", retries_left=0,
        )
        jl.log_skipped("item-4", op="download", reason="dark")
        jl.log_skipped("item-5", op="download", reason="exists")

        st = jl.status()
        assert st["completed"] == 2
        assert st["failed"] == 1
        assert st["skipped"] == 2
        assert st["total_bytes"] == 3000
        assert st["total_files_ok"] == 8
        assert len(st["failed_items"]) == 1
        assert st["failed_items"][0] == ("item-3", "404 Not Found")
        jl.close()

    def test_status_failed_then_completed(self, tmp_path):
        """If an item fails then succeeds, it should count as completed."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)

        jl.log_failed(
            "item-r", op="download", error="Timeout", retries_left=1,
        )
        jl.log_completed(
            "item-r", op="download", destdir="/d", bytes_transferred=500,
            files_ok=2, files_skipped=0, files_failed=0, elapsed=1.0,
        )

        st = jl.status()
        assert st["completed"] == 1
        assert st["failed"] == 0
        assert st["total_bytes"] == 500
        assert st["total_files_ok"] == 2
        assert st["failed_items"] == []
        jl.close()

    def test_status_counts_unique_items(self, tmp_path):
        """Multiple events for same item should be de-duplicated in counts."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)

        jl.log_started(
            "item-1", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=0,
        )
        jl.log_completed(
            "item-1", op="download", destdir="/d", bytes_transferred=100,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=1.0,
        )

        st = jl.status()
        # Should only count as 1 completed, not 1 started + 1 completed
        assert st["completed"] == 1
        jl.close()


class TestJobLogThreadSafety:
    """Tests for thread-safe writes."""

    def test_concurrent_writes(self, tmp_path):
        """Multiple threads writing should not corrupt the JSONL file."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        n_threads = 10
        n_events_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def writer(thread_id):
            barrier.wait()
            for i in range(n_events_per_thread):
                identifier = f"item-t{thread_id}-{i}"
                jl.log_started(
                    identifier, op="download", destdir="/d",
                    est_bytes=100, worker=f"w{thread_id}", retry=0,
                )

        threads = []
        for t in range(n_threads):
            th = threading.Thread(target=writer, args=(t,))
            threads.append(th)
            th.start()

        for th in threads:
            th.join()

        jl.close()

        # All lines should be valid JSON
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == n_threads * n_events_per_thread
        for line in lines:
            rec = json.loads(line)
            assert rec["event"] == "started"

    def test_concurrent_writes_and_reads(self, tmp_path):
        """should_skip should work correctly during concurrent writes."""
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)

        # Pre-populate one completed item
        jl.log_completed(
            "pre-done", op="download", destdir="/d", bytes_transferred=50,
            files_ok=1, files_skipped=0, files_failed=0, elapsed=0.5,
        )

        errors = []

        def reader():
            try:
                for _ in range(100):
                    # should_skip should always be consistent for pre-done
                    assert jl.should_skip("pre-done") is True
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer():
            for i in range(100):
                jl.log_started(
                    f"new-{i}", op="download", destdir="/d",
                    est_bytes=10, worker="w0", retry=0,
                )

        t_reader = threading.Thread(target=reader)
        t_writer = threading.Thread(target=writer)
        t_reader.start()
        t_writer.start()
        t_reader.join()
        t_writer.join()

        jl.close()
        assert errors == [], f"Reader errors: {errors}"


class TestJobLogClose:
    """Tests for close() behavior."""

    def test_close_flushes_data(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "item-1", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=0,
        )
        jl.close()

        # Data should be on disk after close
        content = log_path.read_text()
        assert "item-1" in content

    def test_close_is_idempotent(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "item-1", op="download", destdir="/d", est_bytes=100,
            worker="w0", retry=0,
        )
        jl.close()
        jl.close()  # Should not raise

    def test_context_manager(self, tmp_path):
        """JobLog should work as a context manager."""
        log_path = tmp_path / "job.jsonl"
        with JobLog(log_path) as jl:
            jl.log_started(
                "ctx-item", op="download", destdir="/d", est_bytes=100,
                worker="w0", retry=0,
            )

        content = log_path.read_text()
        assert "ctx-item" in content


class TestJobLogPathTypes:
    """Tests that JobLog accepts both str and Path for log_path."""

    def test_accepts_str_path(self, tmp_path):
        log_path = str(tmp_path / "job.jsonl")
        jl = JobLog(log_path)
        jl.log_started(
            "str-item", op="download", destdir="/d", est_bytes=0,
            worker="w0", retry=0,
        )
        jl.close()
        content = Path(log_path).read_text()
        assert "str-item" in content

    def test_accepts_path_object(self, tmp_path):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_started(
            "path-item", op="download", destdir="/d", est_bytes=0,
            worker="w0", retry=0,
        )
        jl.close()
        content = log_path.read_text()
        assert "path-item" in content


class TestJobLogSkipReasons:
    """Exhaustive tests for all skip reasons."""

    @pytest.mark.parametrize(
        ("reason", "expected_skip"),
        [
            ("exists", True),
            ("dark", True),
            ("empty", True),
            ("no_disk_space", False),
        ],
    )
    def test_skip_reasons(self, tmp_path, reason, expected_skip):
        log_path = tmp_path / "job.jsonl"
        jl = JobLog(log_path)
        jl.log_skipped(f"item-{reason}", op="download", reason=reason)
        assert jl.should_skip(f"item-{reason}") is expected_skip
        jl.close()
