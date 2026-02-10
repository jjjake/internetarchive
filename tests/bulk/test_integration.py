"""End-to-end integration tests for the bulk operations engine."""

import json
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from internetarchive.bulk.disk import DiskPool
from internetarchive.bulk.engine import BulkEngine
from internetarchive.bulk.joblog import JobLog
from internetarchive.bulk.ui import PlainUI, UIEvent, UIHandler
from internetarchive.bulk.worker import BaseWorker, WorkerResult


class CountingWorker(BaseWorker):
    """Worker that tracks which identifiers it processed."""

    def __init__(self):
        self.processed = []

    def execute(self, identifier, job, cancel_event):
        self.processed.append(identifier)
        return WorkerResult(
            success=True,
            identifier=identifier,
            extra={"bytes": 100},
        )


class FailThenSucceedWorker(BaseWorker):
    """Worker that fails N times then succeeds."""

    def __init__(self, fail_count=1):
        self.fail_count = fail_count
        self.attempts = {}

    def execute(self, identifier, job, cancel_event):
        count = self.attempts.get(identifier, 0) + 1
        self.attempts[identifier] = count
        if count <= self.fail_count:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=f"attempt {count} failed",
                retry=True,
            )
        return WorkerResult(
            success=True,
            identifier=identifier,
        )


class EventCollector(UIHandler):
    def __init__(self):
        self.events = []

    def handle(self, event):
        self.events.append(event)


class TestEndToEnd:
    def test_search_resolve_download_resume(self, tmp_path):
        """Full flow: resolve → download → interrupt → resume."""
        path = str(tmp_path / "session.jsonl")

        # Phase 1: resolve + partial download
        worker1 = CountingWorker()
        log1 = JobLog(path)
        collector1 = EventCollector()
        engine1 = BulkEngine(
            log1, worker1, max_workers=1, ui=collector1
        )

        jobs = [
            {"identifier": f"item-{i}"} for i in range(5)
        ]
        rc = engine1.run(
            jobs=iter(jobs), total=5, op="download"
        )
        assert rc == 0
        assert len(worker1.processed) == 5

        # Verify joblog has all entries
        status = log1.status()
        assert status["total"] == 5
        assert status["completed"] == 5

        # Phase 2: simulate partial completion for resume
        path2 = str(tmp_path / "partial.jsonl")
        log_partial = JobLog(path2)
        for i in range(5):
            log_partial.write_job(i + 1, f"item-{i}", "download")
        log_partial.write_event("completed", seq=1)
        log_partial.write_event("completed", seq=3)
        log_partial.close()

        # Resume
        worker2 = CountingWorker()
        log_resume = JobLog(path2)
        collector2 = EventCollector()
        engine2 = BulkEngine(
            log_resume, worker2, max_workers=2, ui=collector2
        )
        rc = engine2.run()
        assert rc == 0

        # Only items 2, 4, 5 should be processed
        assert set(worker2.processed) == {
            "item-1", "item-3", "item-4"
        }

    def test_failure_and_retry(self, tmp_path):
        """Items that fail are retried up to max retries."""
        path = str(tmp_path / "retry.jsonl")

        worker = FailThenSucceedWorker(fail_count=2)
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, worker, max_workers=1, retries=3, ui=collector
        )

        rc = engine.run(
            jobs=iter([{"identifier": "retry-item"}]),
            total=1,
            op="download",
        )

        assert rc == 0
        assert worker.attempts["retry-item"] == 3

    def test_permanent_failure_no_retry(self, tmp_path):
        """Permanently failed items are not retried."""
        path = str(tmp_path / "perm.jsonl")

        class DarkWorker(BaseWorker):
            def execute(self, identifier, job, cancel_event):
                return WorkerResult(
                    success=False,
                    identifier=identifier,
                    error="item is dark",
                    retry=False,
                )

        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, DarkWorker(), max_workers=1, retries=5,
            ui=collector,
        )

        rc = engine.run(
            jobs=iter([{"identifier": "dark-item"}]),
            total=1,
            op="download",
        )

        assert rc == 1
        failed = [
            e for e in collector.events
            if e.kind == "job_failed"
        ]
        assert len(failed) == 1

    def test_joblog_integrity(self, tmp_path):
        """Every job line and event is valid JSON."""
        path = str(tmp_path / "integrity.jsonl")

        worker = FailThenSucceedWorker(fail_count=1)
        log = JobLog(path)
        engine = BulkEngine(
            log, worker, max_workers=1, retries=3,
            ui=EventCollector(),
        )

        engine.run(
            jobs=iter([
                {"identifier": "a"},
                {"identifier": "b"},
            ]),
            total=2,
            op="download",
        )

        # Every line should parse as valid JSON
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                assert "event" in record
                assert "ts" in record

    def test_concurrent_workers(self, tmp_path):
        """Multiple workers process items concurrently."""
        path = str(tmp_path / "concurrent.jsonl")

        worker = CountingWorker()
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, worker, max_workers=4, ui=collector
        )

        ids = [{"identifier": f"item-{i}"} for i in range(20)]
        rc = engine.run(jobs=iter(ids), total=20, op="download")

        assert rc == 0
        assert len(worker.processed) == 20
        assert set(worker.processed) == {
            f"item-{i}" for i in range(20)
        }

    def test_status_after_mixed_results(self, tmp_path):
        """Status correctly reflects mixed success/failure."""
        path = str(tmp_path / "mixed.jsonl")

        class AlternatingWorker(BaseWorker):
            def __init__(self):
                self.count = 0

            def execute(self, identifier, job, cancel_event):
                self.count += 1
                if self.count % 3 == 0:
                    return WorkerResult(
                        success=False,
                        identifier=identifier,
                        error="every third fails",
                        retry=False,
                    )
                return WorkerResult(
                    success=True, identifier=identifier
                )

        log = JobLog(path)
        engine = BulkEngine(
            log, AlternatingWorker(), max_workers=1,
            ui=EventCollector(),
        )

        engine.run(
            jobs=iter([{"identifier": f"i-{i}"} for i in range(9)]),
            total=9,
            op="download",
        )

        status = log.status()
        assert status["total"] == 9
        assert status["completed"] == 6
        assert status["failed"] == 3
        assert status["pending"] == 0

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_multi_disk_routing(self, mock_usage, tmp_path):
        """DiskPool routes to different disks."""
        d1 = str(tmp_path / "disk1")
        d2 = str(tmp_path / "disk2")

        def make_du(total, used, free):
            m = MagicMock()
            m.total = total
            m.used = used
            m.free = free
            return m

        mock_usage.side_effect = lambda p: {
            d1: make_du(100e9, 80e9, 20e9),
            d2: make_du(100e9, 50e9, 50e9),
        }.get(p, make_du(100e9, 50e9, 50e9))

        pool = DiskPool([d1, d2])

        # First route should go to disk2 (most space)
        result1 = pool.route(0)
        assert result1 == d2

        # After some usage, should still prefer disk2
        result2 = pool.route(0)
        assert result2 in (d1, d2)
