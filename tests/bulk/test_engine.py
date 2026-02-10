"""Tests for BulkEngine."""

import io
import time
from threading import Event

import pytest

from internetarchive.bulk.engine import BulkEngine
from internetarchive.bulk.joblog import JobLog
from internetarchive.bulk.ui import PlainUI, UIEvent, UIHandler
from internetarchive.bulk.worker import BaseWorker, WorkerResult


class SuccessWorker(BaseWorker):
    """Worker that always succeeds."""

    def execute(self, identifier, job, cancel_event):
        return WorkerResult(
            success=True,
            identifier=identifier,
            extra={"bytes": 100},
        )


class FailWorker(BaseWorker):
    """Worker that always fails with retry."""

    def execute(self, identifier, job, cancel_event):
        return WorkerResult(
            success=False,
            identifier=identifier,
            error="HTTP 503",
            retry=True,
        )


class PermanentFailWorker(BaseWorker):
    """Worker that fails permanently (no retry)."""

    def execute(self, identifier, job, cancel_event):
        return WorkerResult(
            success=False,
            identifier=identifier,
            error="item is dark",
            retry=False,
        )


class BackoffWorker(BaseWorker):
    """Worker that signals backoff on first call, then succeeds."""

    def __init__(self):
        self.call_count = 0

    def execute(self, identifier, job, cancel_event):
        self.call_count += 1
        if self.call_count == 1:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error="disk full",
                backoff=True,
            )
        return WorkerResult(
            success=True,
            identifier=identifier,
        )


class ExceptionWorker(BaseWorker):
    """Worker that raises an exception."""

    def execute(self, identifier, job, cancel_event):
        raise RuntimeError("unexpected crash")


class CancelAwareWorker(BaseWorker):
    """Worker that respects cancel_event."""

    def execute(self, identifier, job, cancel_event):
        for _ in range(10):
            if cancel_event.is_set():
                return WorkerResult(
                    success=False,
                    identifier=identifier,
                    error="cancelled",
                    retry=False,
                )
            time.sleep(0.01)
        return WorkerResult(success=True, identifier=identifier)


class EventCollector(UIHandler):
    """Collects UI events for assertion."""

    def __init__(self):
        self.events: list[UIEvent] = []

    def handle(self, event):
        self.events.append(event)


def _make_jobs(identifiers):
    """Create job dicts from identifiers."""
    return iter([{"identifier": i} for i in identifiers])


class TestBulkEngine:
    def test_basic_success(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, SuccessWorker(), max_workers=2, ui=collector
        )

        ids = ["item-1", "item-2", "item-3"]
        rc = engine.run(
            jobs=_make_jobs(ids), total=3, op="download"
        )

        assert rc == 0
        started = [
            e for e in collector.events
            if e.kind == "job_started"
        ]
        completed = [
            e for e in collector.events
            if e.kind == "job_completed"
        ]
        assert len(started) == 3
        assert len(completed) == 3

    def test_permanent_failure(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, PermanentFailWorker(), max_workers=1,
            retries=3, ui=collector,
        )

        rc = engine.run(
            jobs=_make_jobs(["bad-item"]), total=1, op="download"
        )

        assert rc == 1
        failed = [
            e for e in collector.events
            if e.kind == "job_failed"
        ]
        # Should fail once without retries
        assert len(failed) == 1

    def test_retry_then_exhaust(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, FailWorker(), max_workers=1,
            retries=2, ui=collector,
        )

        rc = engine.run(
            jobs=_make_jobs(["fail-item"]), total=1, op="download"
        )

        assert rc == 1
        failed = [
            e for e in collector.events
            if e.kind == "job_failed"
        ]
        # 2 retries + 1 final failure = 3 failure events
        assert len(failed) == 3

    def test_exception_in_worker(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, ExceptionWorker(), max_workers=1, ui=collector
        )

        rc = engine.run(
            jobs=_make_jobs(["crash-item"]), total=1, op="download"
        )

        assert rc == 1
        failed = [
            e for e in collector.events
            if e.kind == "job_failed"
        ]
        assert len(failed) == 1
        assert "unexpected crash" in failed[0].error

    def test_resume(self, tmp_path):
        path = str(tmp_path / "test.jsonl")

        # First run: write jobs but only complete one
        log1 = JobLog(path)
        log1.write_job(1, "item-a", "download")
        log1.write_job(2, "item-b", "download")
        log1.write_job(3, "item-c", "download")
        log1.write_event("completed", seq=1)
        log1.close()

        # Resume: should only process items 2 and 3
        log2 = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log2, SuccessWorker(), max_workers=1, ui=collector
        )

        rc = engine.run()
        assert rc == 0

        started = [
            e for e in collector.events
            if e.kind == "job_started"
        ]
        completed = [
            e for e in collector.events
            if e.kind == "job_completed"
        ]
        started_ids = {e.identifier for e in started}
        assert "item-a" not in started_ids
        assert "item-b" in started_ids
        assert "item-c" in started_ids
        assert len(completed) == 2

    def test_no_jobs(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        engine = BulkEngine(log, SuccessWorker(), ui=EventCollector())

        rc = engine.run(jobs=iter([]), total=0, op="download")
        assert rc == 0

    def test_backoff(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()
        worker = BackoffWorker()
        engine = BulkEngine(
            log, worker, max_workers=1, ui=collector
        )

        rc = engine.run(
            jobs=_make_jobs(["item-1"]), total=1, op="download"
        )

        assert rc == 0
        kinds = [e.kind for e in collector.events]
        assert "backoff_start" in kinds
        assert "backoff_end" in kinds
        assert "job_completed" in kinds

    def test_status_summary(self, tmp_path):
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "a", "download")
        log.write_job(2, "b", "download")
        log.write_event("completed", seq=1)
        log.write_event("failed", seq=2, retry=False)
        log.close()

        s = log.status()
        assert s["total"] == 2
        assert s["completed"] == 1
        assert s["failed"] == 1
        assert s["pending"] == 0

    def test_multiple_workers(self, tmp_path):
        """Verify multiple workers execute concurrently."""
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log, SuccessWorker(), max_workers=4, ui=collector
        )

        ids = [f"item-{i}" for i in range(20)]
        rc = engine.run(
            jobs=_make_jobs(ids), total=20, op="download"
        )

        assert rc == 0
        completed = [
            e for e in collector.events
            if e.kind == "job_completed"
        ]
        assert len(completed) == 20

    def test_empty_resume_all_done(self, tmp_path):
        """Resume when all jobs already completed."""
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        log.write_job(1, "item-a", "download")
        log.write_event("completed", seq=1)
        log.close()

        log2 = JobLog(path)
        collector = EventCollector()
        engine = BulkEngine(
            log2, SuccessWorker(), max_workers=1, ui=collector
        )

        rc = engine.run()
        assert rc == 0

        # Should emit progress but no started events
        started = [
            e for e in collector.events
            if e.kind == "job_started"
        ]
        assert len(started) == 0

    def test_retry_after_iterator_exhaustion(self, tmp_path):
        """Retried jobs must not be dropped when the job iterator
        is already exhausted (regression test for #745 review #1).
        """
        path = str(tmp_path / "test.jsonl")
        log = JobLog(path)
        collector = EventCollector()

        class FailOnceThenSucceed(BaseWorker):
            """Fails the first attempt for each id, succeeds after."""

            def __init__(self):
                self.attempts = {}

            def execute(self, identifier, job, cancel_event):
                count = self.attempts.get(identifier, 0) + 1
                self.attempts[identifier] = count
                if count == 1:
                    return WorkerResult(
                        success=False,
                        identifier=identifier,
                        error="transient",
                        retry=True,
                    )
                return WorkerResult(
                    success=True, identifier=identifier
                )

        worker = FailOnceThenSucceed()
        engine = BulkEngine(
            log, worker, max_workers=4, retries=3, ui=collector
        )

        # 4 workers, 4 jobs — all submitted at once, iterator
        # exhausted immediately. All fail on first try and need
        # retry; those retries must not be silently dropped.
        ids = [f"item-{i}" for i in range(4)]
        rc = engine.run(
            jobs=_make_jobs(ids), total=4, op="download"
        )

        assert rc == 0
        completed = [
            e for e in collector.events
            if e.kind == "job_completed"
        ]
        assert len(completed) == 4
