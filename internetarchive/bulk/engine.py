"""
internetarchive.bulk.engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bulk operations engine orchestrator.

Operation-ignorant — manages concurrency, retries, backoff, and the
joblog. Workers handle the actual operation logic.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import signal
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from threading import Event
from typing import Iterator

from internetarchive.bulk.joblog import JobLog
from internetarchive.bulk.ui import PlainUI, UIEvent, UIHandler
from internetarchive.bulk.worker import BaseWorker, WorkerResult


class BulkEngine:
    """Orchestrator for bulk operations.

    :param joblog: ``JobLog`` instance for recording jobs and events.
    :param worker: ``BaseWorker`` implementation to execute jobs.
    :param max_workers: Number of concurrent worker threads.
    :param retries: Maximum retry attempts per job.
    :param ui: ``UIHandler`` for progress display. Defaults to
        ``PlainUI``.
    """

    def __init__(
        self,
        joblog: JobLog,
        worker: BaseWorker,
        max_workers: int = 1,
        retries: int = 3,
        ui: UIHandler | None = None,
    ):
        self.joblog = joblog
        self.worker = worker
        self.max_workers = max_workers
        self.retries = retries
        self.ui = ui or PlainUI()
        self._cancel = Event()
        self._completed = 0
        self._failed = 0
        self._skipped = 0
        self._total = 0

    def _emit(self, event: UIEvent) -> None:
        """Emit a UI event to the handler."""
        self.ui.handle(event)

    def resolve(
        self,
        jobs: Iterator[dict],
        total: int,
        op: str,
        resume: bool = False,
    ) -> None:
        """Resolve phase: write job lines to the joblog.

        On resume, this is skipped — jobs are already in the log.

        :param jobs: Iterator yielding dicts. Each dict must have
            an ``"id"`` key used as the job identifier in the log.
        :param total: Total number of items expected.
        :param op: Operation name (e.g. ``"download"``).
        :param resume: If ``True``, skip writing job lines.
        """
        if resume:
            return
        seq = self.joblog.get_max_seq()
        for item in jobs:
            if self._cancel.is_set():
                break
            seq += 1
            job_id = item.get("id", item.get("identifier", ""))
            self.joblog.write_job(seq, job_id, op)

    def run(
        self,
        jobs: Iterator[dict] | None = None,
        total: int = 0,
        op: str = "download",
    ) -> int:
        """Run the bulk operation.

        If the joblog already has entries, this is a resume. Otherwise,
        ``jobs`` and ``total`` must be provided for the resolve phase.

        :param jobs: Iterator of job dicts (for initial run).
        :param total: Total number of items.
        :param op: Operation name.
        :returns: Exit code (0 = all succeeded, 1 = any failed).
        """
        # Install signal handler for graceful shutdown
        original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_sigint)

        try:
            return self._run(jobs, total, op)
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self.joblog.close()

    def _run(
        self,
        jobs: Iterator[dict] | None,
        total: int,
        op: str,
    ) -> int:
        """Internal run implementation."""
        # Determine if this is a resume (single-pass scan)
        snapshot = self.joblog.load()
        resume = snapshot["max_seq"] > 0

        if resume:
            pending_jobs = snapshot["pending"]
            status = snapshot["status"]
            self._total = status["total"]
            self._completed = status["completed"]
            self._failed = status["failed"]
        else:
            if jobs is None:
                print("error: no jobs to process", file=sys.stderr)
                return 1
            # Resolve phase
            self.resolve(jobs, total, op)
            self._total = total if total else self.joblog.get_max_seq()
            snapshot = self.joblog.load()
            pending_jobs = snapshot["pending"]

        if not pending_jobs:
            self._emit(UIEvent(
                kind="progress",
                total=self._total,
                extra={
                    "completed": self._completed,
                    "failed": self._failed,
                    "pending": 0,
                },
            ))
            return 0 if self._failed == 0 else 1

        return self._execute(pending_jobs)

    def _execute(self, pending_jobs: list[dict]) -> int:
        """Execute phase: process pending jobs with thread pool."""
        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as pool:
            futures: dict[Future, tuple[dict, float]] = {}
            job_retries: dict[int, int] = {}
            # Separate queue for retried/backoff jobs so we never
            # re-iterate already-processed items from pending_jobs.
            retry_queue: list[dict] = []
            backoff_active = False
            job_iter = iter(pending_jobs)
            exhausted = False

            while True:
                if self._cancel.is_set() and not futures:
                    break

                # Submit new jobs up to max_workers.
                # Drain retry_queue first, then pull from job_iter.
                while (
                    not self._cancel.is_set()
                    and not backoff_active
                    and len(futures) < self.max_workers
                ):
                    job = None
                    if retry_queue:
                        job = retry_queue.pop(0)
                    elif not exhausted:
                        try:
                            job = next(job_iter)
                        except StopIteration:
                            exhausted = True
                    if job is None:
                        break

                    seq = job["seq"]
                    identifier = job.get("id", "")
                    worker_idx = len(futures) % self.max_workers

                    self.joblog.write_event(
                        "started", seq=seq, worker=worker_idx
                    )
                    self._emit(UIEvent(
                        kind="job_started",
                        seq=seq,
                        total=self._total,
                        identifier=identifier,
                        worker=worker_idx,
                    ))

                    future = pool.submit(
                        self.worker.execute,
                        job,
                        self._cancel,
                    )
                    futures[future] = (job, time.monotonic())

                if not futures:
                    break

                # Wait for at least one future to complete
                done, _ = wait(futures, timeout=0.5)

                for future in done:
                    job, submit_time = futures.pop(future)
                    seq = job["seq"]
                    identifier = job.get("id", "")

                    try:
                        result: WorkerResult = future.result()
                    except Exception as exc:
                        self._handle_exception(
                            seq, identifier, exc,
                        )
                        continue

                    elapsed = time.monotonic() - submit_time

                    if result.success:
                        self.joblog.write_event(
                            "completed",
                            seq=seq,
                            extra=result.extra,
                        )
                        self._completed += 1
                        self._emit(UIEvent(
                            kind="job_completed",
                            seq=seq,
                            total=self._total,
                            identifier=identifier,
                            extra=result.extra or {},
                            elapsed=elapsed,
                        ))
                    elif result.backoff:
                        backoff_active = True
                        self._emit(UIEvent(
                            kind="backoff_start",
                            error=result.error or "backoff requested",
                        ))
                        # Re-queue this job for retry after backoff
                        retry_queue.append(job)
                    else:
                        attempt = job_retries.get(seq, 0) + 1
                        job_retries[seq] = attempt

                        if result.retry and attempt <= self.retries:
                            self.joblog.write_event(
                                "failed",
                                seq=seq,
                                error=result.error,
                                retry=attempt,
                            )
                            self._emit(UIEvent(
                                kind="job_failed",
                                seq=seq,
                                total=self._total,
                                identifier=identifier,
                                error=result.error or "",
                                retry=attempt,
                                max_retries=self.retries,
                            ))
                            # Re-queue for retry
                            retry_queue.append(job)
                        else:
                            self.joblog.write_event(
                                "failed",
                                seq=seq,
                                error=result.error,
                                retry=False,
                            )
                            self._failed += 1
                            self._emit(UIEvent(
                                kind="job_failed",
                                seq=seq,
                                total=self._total,
                                identifier=identifier,
                                error=result.error or "",
                            ))

                # Check if backoff can be released
                if backoff_active and not futures:
                    backoff_active = False
                    self._emit(UIEvent(kind="backoff_end"))

        return 0 if self._failed == 0 else 1

    def _handle_exception(
        self,
        seq: int,
        identifier: str,
        exc: Exception,
    ) -> None:
        """Handle an unhandled exception from a worker."""
        error = str(exc)
        self.joblog.write_event(
            "failed", seq=seq, error=error, retry=False
        )
        self._failed += 1
        self._emit(UIEvent(
            kind="job_failed",
            seq=seq,
            total=self._total,
            identifier=identifier,
            error=error,
        ))

    def _handle_sigint(self, signum, frame) -> None:
        """Handle SIGINT for graceful shutdown."""
        if not self._cancel.is_set():
            print(
                "\nShutting down gracefully... "
                "(waiting for in-flight jobs to finish)",
                file=sys.stderr,
            )
            self._cancel.set()
        else:
            # Second Ctrl+C: force exit
            sys.exit(1)
