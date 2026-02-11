"""Tests for JobLog and Bitmap."""

import json
import os
import threading

import pytest

from internetarchive.bulk.joblog import Bitmap, JobLog


class TestBitmap:
    def test_set_and_contains(self):
        b = Bitmap(100)
        assert 0 not in b
        assert 50 not in b
        b.set(0)
        b.set(50)
        assert 0 in b
        assert 50 in b
        assert 1 not in b

    def test_auto_grow(self):
        b = Bitmap(0)
        b.set(1000)
        assert 1000 in b
        assert 999 not in b

    def test_large_scale(self):
        """Bitmap at 10M scale uses ~1.2MB memory."""
        b = Bitmap(10_000_000)
        # Verify size is ~1.2MB
        assert b.size_bytes == (10_000_000 + 7) // 8  # 1,250,000 bytes
        b.set(0)
        b.set(9_999_999)
        assert 0 in b
        assert 9_999_999 in b
        assert 5_000_000 not in b

    def test_empty_bitmap(self):
        b = Bitmap()
        assert 0 not in b
        assert 100 not in b

    def test_boundary_values(self):
        b = Bitmap(16)
        # Test at byte boundaries
        for i in [7, 8, 15]:
            b.set(i)
            assert i in b

    def test_negative_index_set_raises(self):
        b = Bitmap(16)
        with pytest.raises(ValueError, match="non-negative"):
            b.set(-1)

    def test_negative_index_contains(self):
        b = Bitmap(16)
        assert -1 not in b
        assert -100 not in b


class TestJobLog:
    def test_write_and_read_jobs(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_job(2, "item-b", "download")
        log.close()

        # Read back
        with open(path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 2
        assert lines[0]["event"] == "job"
        assert lines[0]["seq"] == 1
        assert lines[0]["id"] == "item-a"
        assert lines[0]["op"] == "download"
        assert "ts" in lines[0]
        assert lines[1]["seq"] == 2

    def test_write_events(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_event("started", seq=1, worker=0)
        log.write_event(
            "completed", seq=1, extra={"bytes": 1024}
        )
        log.close()

        with open(path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 3
        assert lines[1]["event"] == "started"
        assert lines[1]["worker"] == 0
        assert lines[2]["event"] == "completed"
        assert lines[2]["extra"] == {"bytes": 1024}

    def test_resume_bitmap_completed(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_job(2, "item-b", "download")
        log.write_job(3, "item-c", "download")
        log.write_event("completed", seq=1)
        log.write_event("completed", seq=3)
        log.close()

        bitmap = log.build_resume_bitmap()
        assert 1 in bitmap
        assert 2 not in bitmap
        assert 3 in bitmap

    def test_resume_bitmap_permanent_failure(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_event("failed", seq=1, retry=False)
        log.close()

        bitmap = log.build_resume_bitmap()
        assert 1 in bitmap  # permanently failed = done

    def test_resume_bitmap_retryable_failure(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_event("failed", seq=1, error="503", retry=1)
        log.close()

        bitmap = log.build_resume_bitmap()
        assert 1 not in bitmap  # still pending

    def test_iter_pending_jobs(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "done", "download")
        log.write_job(2, "pending", "download")
        log.write_job(3, "also-done", "download")
        log.write_event("completed", seq=1)
        log.write_event("completed", seq=3)
        log.close()

        bitmap = log.build_resume_bitmap()
        pending = list(log.iter_pending_jobs(bitmap))
        assert len(pending) == 1
        assert pending[0]["id"] == "pending"
        assert pending[0]["seq"] == 2

    def test_malformed_trailing_line(self, tmp_path):
        """Crash recovery: malformed trailing line is skipped."""
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.close()

        # Simulate crash: append partial JSON
        with open(path, "a") as f:
            f.write('{"event":"job","seq":2,"id":"item-b",\n')

        bitmap = log.build_resume_bitmap()
        pending = list(log.iter_pending_jobs(bitmap))
        assert len(pending) == 1
        assert pending[0]["id"] == "item-a"

    def test_get_max_seq(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "a", "download")
        log.write_job(2, "b", "download")
        log.write_job(5, "c", "download")
        log.close()
        assert log.get_max_seq() == 5

    def test_get_max_seq_empty(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        assert log.get_max_seq() == 0

    def test_status(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "a", "download")
        log.write_job(2, "b", "download")
        log.write_job(3, "c", "download")
        log.write_event("completed", seq=1)
        log.write_event("failed", seq=2, retry=False)
        log.close()

        s = log.status()
        assert s == {
            "total": 3,
            "completed": 1,
            "failed": 1,
            "pending": 1,
        }

    def test_status_empty(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        s = log.status()
        assert s == {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
        }

    def test_thread_safety(self, tmp_path):
        """Multiple threads writing concurrently shouldn't corrupt."""
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)

        def write_jobs(start, count):
            for i in range(start, start + count):
                log.write_job(i, f"item-{i}", "download")

        threads = [
            threading.Thread(target=write_jobs, args=(i * 100, 100))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        log.close()

        # All 400 lines should be valid JSON
        with open(path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 400

    def test_nonexistent_file_build_bitmap(self, tmp_path):
        path = str(tmp_path / "does_not_exist.jsonl")
        log = JobLog(path)
        bitmap = log.build_resume_bitmap()
        assert 0 not in bitmap

    def test_extra_fields_in_job(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(
            1, "item-a", "download", destdir="/mnt/disk1"
        )
        log.close()

        with open(path) as f:
            record = json.loads(f.readline())
        assert record["destdir"] == "/mnt/disk1"
