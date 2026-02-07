from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from internetarchive.bulk.disk import DiskPool
from internetarchive.bulk.engine import BulkEngine
from internetarchive.bulk.jobs import JobLog
from internetarchive.bulk.ui.base import UIEvent
from internetarchive.bulk.worker import (
    BaseWorker,
    VerifyResult,
    WorkerResult,
)

# -------------------------------------------------------------------
# Helper: fake statvfs (same pattern as test_disk.py)
# -------------------------------------------------------------------


class FakeStatvfs:
    """Minimal os.statvfs result with controllable free space."""

    def __init__(self, free_bytes: int, block_size: int = 4096):
        self.f_frsize = block_size
        self.f_bavail = free_bytes // block_size


def make_statvfs_map(mapping: dict[str, int]):
    """Return a callable mapping directory paths to fake statvfs."""

    def _fake_statvfs(path: str) -> FakeStatvfs:
        for dir_path, free in mapping.items():
            if path == dir_path:
                return FakeStatvfs(free)
        raise OSError(f"No fake statvfs for {path}")

    return _fake_statvfs


# -------------------------------------------------------------------
# Concrete test workers
# -------------------------------------------------------------------


class SuccessWorker(BaseWorker):
    """Worker that always succeeds."""

    def __init__(
        self,
        size: int = 1024,
        files_ok: int = 3,
    ):
        self._size = size
        self._files_ok = files_ok

    def estimate_size(self, identifier: str) -> int | None:
        return self._size

    def execute(
        self, identifier: str, destdir: Path
    ) -> WorkerResult:
        return WorkerResult(
            success=True,
            identifier=identifier,
            bytes_transferred=self._size,
            files_ok=self._files_ok,
            files_skipped=0,
            files_failed=0,
        )

    def verify(
        self, identifier: str, destdir: Path
    ) -> VerifyResult:
        return VerifyResult(
            identifier=identifier,
            complete=True,
            files_expected=self._files_ok,
            files_found=self._files_ok,
        )


class FailWorker(BaseWorker):
    """Worker that always fails with a WorkerResult."""

    def __init__(self, error: str = "simulated failure"):
        self._error = error

    def estimate_size(self, identifier: str) -> int | None:
        return 1024

    def execute(
        self, identifier: str, destdir: Path
    ) -> WorkerResult:
        return WorkerResult(
            success=False,
            identifier=identifier,
            error=self._error,
        )

    def verify(
        self, identifier: str, destdir: Path
    ) -> VerifyResult:
        return VerifyResult(
            identifier=identifier,
            complete=False,
            files_expected=0,
            files_found=0,
        )


class FailThenSucceedWorker(BaseWorker):
    """Worker that fails N times then succeeds."""

    def __init__(self, fail_count: int = 1, size: int = 512):
        self._fail_count = fail_count
        self._size = size
        self._lock = threading.Lock()
        self._attempts: dict[str, int] = {}

    def estimate_size(self, identifier: str) -> int | None:
        return self._size

    def execute(
        self, identifier: str, destdir: Path
    ) -> WorkerResult:
        with self._lock:
            attempts = self._attempts.get(identifier, 0)
            self._attempts[identifier] = attempts + 1

        if attempts < self._fail_count:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=f"fail #{attempts + 1}",
            )
        return WorkerResult(
            success=True,
            identifier=identifier,
            bytes_transferred=self._size,
            files_ok=1,
            files_skipped=0,
            files_failed=0,
        )

    def verify(
        self, identifier: str, destdir: Path
    ) -> VerifyResult:
        return VerifyResult(
            identifier=identifier,
            complete=True,
            files_expected=1,
            files_found=1,
        )


class SlowWorker(BaseWorker):
    """Worker that takes a configurable time to complete."""

    def __init__(self, delay: float = 0.1, size: int = 256):
        self._delay = delay
        self._size = size

    def estimate_size(self, identifier: str) -> int | None:
        return self._size

    def execute(
        self, identifier: str, destdir: Path
    ) -> WorkerResult:
        time.sleep(self._delay)
        return WorkerResult(
            success=True,
            identifier=identifier,
            bytes_transferred=self._size,
            files_ok=1,
            files_skipped=0,
            files_failed=0,
        )

    def verify(
        self, identifier: str, destdir: Path
    ) -> VerifyResult:
        return VerifyResult(
            identifier=identifier,
            complete=True,
            files_expected=1,
            files_found=1,
        )


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

PLENTY_OF_SPACE = 100 * 1024**3  # 100 GiB


@pytest.fixture
def job_log(tmp_path):
    """Create a fresh JobLog in a temporary directory."""
    log = JobLog(tmp_path / "jobs.jsonl")
    yield log
    log.close()


@pytest.fixture
def disk_pool():
    """DiskPool with space checks disabled (always routes to /dst)."""
    return DiskPool(destdirs=["/dst"], disabled=True)


@pytest.fixture
def statvfs_plenty():
    """Patch os.statvfs to report plenty of free space on /dst."""
    fake = make_statvfs_map({"/dst": PLENTY_OF_SPACE})
    with patch("os.statvfs", side_effect=fake):
        yield


# ===================================================================
# TestEngineBasic
# ===================================================================


class TestEngineBasic:
    """Basic engine behaviour: download, skip, failure tracking."""

    def test_downloads_all_items(self, job_log, disk_pool):
        """All items should complete when the worker succeeds."""
        worker = SuccessWorker(size=2048, files_ok=5)
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
        )
        result = engine.run(["item-a", "item-b", "item-c"])
        assert result["completed"] == 3
        assert result["failed"] == 0
        assert result["skipped"] == 0

    def test_failed_items_tracked(self, job_log, disk_pool):
        """Failed items should be counted in the result."""
        worker = FailWorker(error="connection reset")
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            job_retries=0,
            op="download",
        )
        result = engine.run(["bad-1", "bad-2"])
        assert result["failed"] == 2
        assert result["completed"] == 0

    def test_resume_skips_completed(self, tmp_path, disk_pool):
        """Items already completed in the job log are skipped."""
        log_path = tmp_path / "resume.jsonl"

        # First run: complete item-a.
        log1 = JobLog(log_path)
        worker = SuccessWorker()
        engine1 = BulkEngine(
            worker=worker,
            job_log=log1,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
        )
        engine1.run(["item-a"])
        log1.close()

        # Second run: item-a should be skipped.
        log2 = JobLog(log_path)
        engine2 = BulkEngine(
            worker=worker,
            job_log=log2,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
        )
        result = engine2.run(["item-a", "item-b"])
        assert result["skipped"] == 1
        assert result["completed"] == 1
        log2.close()

    def test_no_disk_space_skips_item(
        self, job_log, statvfs_plenty
    ):
        """Items are skipped when no disk has enough space."""
        # Create a pool with real space checks (not disabled)
        # but very low free space reported.
        tiny_space = make_statvfs_map({"/full": 100})
        with patch("os.statvfs", side_effect=tiny_space):
            pool = DiskPool(
                destdirs=["/full"],
                margin=1024**3,
                disabled=False,
            )
            worker = SuccessWorker(size=10 * 1024**3)
            engine = BulkEngine(
                worker=worker,
                job_log=job_log,
                disk_pool=pool,
                num_workers=1,
                op="download",
            )
            result = engine.run(["big-item"])

        assert result["skipped"] == 1
        assert result["completed"] == 0
        assert result["failed"] == 0

    def test_ui_events_emitted(self, job_log, disk_pool):
        """UI handler receives events for started and completed."""
        events: list[UIEvent] = []
        worker = SuccessWorker()
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
            ui_handler=events.append,
        )
        engine.run(["item-x"])
        kinds = [e.kind for e in events]
        assert "item_started" in kinds
        assert "item_completed" in kinds

    def test_empty_identifiers(self, job_log, disk_pool):
        """Running with no identifiers returns zero counts."""
        worker = SuccessWorker()
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
        )
        result = engine.run([])
        assert result == {
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }

    def test_mixed_success_and_failure(
        self, job_log, disk_pool
    ):
        """Engine tracks both successes and failures correctly."""

        class MixedWorker(BaseWorker):
            """Fails on identifiers containing 'bad'."""

            def estimate_size(self, identifier: str) -> int | None:
                return 100

            def execute(
                self, identifier: str, destdir: Path
            ) -> WorkerResult:
                if "bad" in identifier:
                    return WorkerResult(
                        success=False,
                        identifier=identifier,
                        error="bad item",
                    )
                return WorkerResult(
                    success=True,
                    identifier=identifier,
                    bytes_transferred=100,
                    files_ok=1,
                )

            def verify(
                self, identifier: str, destdir: Path
            ) -> VerifyResult:
                return VerifyResult(
                    identifier=identifier,
                    complete=True,
                    files_expected=1,
                    files_found=1,
                )

        engine = BulkEngine(
            worker=MixedWorker(),
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            job_retries=0,
            op="download",
        )
        result = engine.run(["good-1", "bad-1", "good-2", "bad-2"])
        assert result["completed"] == 2
        assert result["failed"] == 2


# ===================================================================
# TestEngineRetry
# ===================================================================


class TestEngineRetry:
    """Retry behaviour for failed items."""

    def test_retries_failed_items(self, job_log, disk_pool):
        """Items that fail are retried and eventually succeed."""
        worker = FailThenSucceedWorker(fail_count=2, size=512)
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            job_retries=3,
            op="download",
        )
        result = engine.run(["flaky-item"])
        assert result["completed"] == 1
        assert result["failed"] == 0

    def test_retries_exhausted(self, job_log, disk_pool):
        """Items that exhaust all retries are counted as failed."""
        worker = FailWorker(error="persistent failure")
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            job_retries=2,
            op="download",
        )
        result = engine.run(["doomed-item"])
        assert result["failed"] == 1
        assert result["completed"] == 0

    def test_retry_count_in_log(self, tmp_path, disk_pool):
        """Each retry attempt logs the correct retry number."""
        log_path = tmp_path / "retries.jsonl"
        log = JobLog(log_path)
        worker = FailThenSucceedWorker(fail_count=1, size=100)
        engine = BulkEngine(
            worker=worker,
            job_log=log,
            disk_pool=disk_pool,
            num_workers=1,
            job_retries=2,
            op="download",
        )
        engine.run(["retry-me"])
        log.close()

        # Read the JSONL and check retry values.
        lines = log_path.read_text().strip().split("\n")
        records = [json.loads(line) for line in lines]
        started_records = [
            r for r in records if r["event"] == "started"
        ]
        # Should have two started records: retry 0 and retry 1.
        assert len(started_records) == 2
        assert started_records[0]["retry"] == 0
        assert started_records[1]["retry"] == 1


# ===================================================================
# TestEngineConcurrency
# ===================================================================


class TestEngineConcurrency:
    """Concurrency and thread-pool behaviour."""

    def test_parallel_execution(self, job_log, disk_pool):
        """Multiple workers should run concurrently."""
        worker = SlowWorker(delay=0.1, size=100)
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=4,
            op="download",
        )
        items = [f"item-{i}" for i in range(8)]
        t0 = time.monotonic()
        result = engine.run(items)
        elapsed = time.monotonic() - t0

        assert result["completed"] == 8

        # With 8 items, 0.1s each, 4 workers: ~0.2s ideal.
        # Sequential would be ~0.8s. Allow generous margin.
        assert elapsed < 0.6, (
            f"Expected parallel execution but took {elapsed:.2f}s"
        )

    def test_request_stop(self, job_log, disk_pool):
        """request_stop() prevents new items from being submitted."""
        worker = SlowWorker(delay=0.2, size=100)
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
        )

        # Request stop immediately from another thread.
        def stop_soon():
            time.sleep(0.05)
            engine.request_stop()

        stopper = threading.Thread(target=stop_soon)
        stopper.start()

        items = [f"item-{i}" for i in range(20)]
        result = engine.run(items)
        stopper.join()

        total_processed = (
            result["completed"]
            + result["failed"]
            + result["skipped"]
        )
        # Should have processed fewer than all 20.
        assert total_processed < 20

    def test_pause_resume(self, job_log, disk_pool):
        """pause() and resume() control the submission flow."""
        events: list[UIEvent] = []
        worker = SlowWorker(delay=0.05, size=100)
        engine = BulkEngine(
            worker=worker,
            job_log=job_log,
            disk_pool=disk_pool,
            num_workers=1,
            op="download",
            ui_handler=events.append,
        )

        def pause_then_resume():
            time.sleep(0.02)
            engine.pause()
            time.sleep(0.15)
            engine.resume()

        controller = threading.Thread(target=pause_then_resume)
        controller.start()

        result = engine.run(["p-1", "p-2", "p-3"])
        controller.join()

        # All items should eventually complete.
        assert result["completed"] == 3
