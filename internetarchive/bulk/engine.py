#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.bulk.engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Concurrent bulk operation engine using ThreadPoolExecutor.

The :class:`BulkEngine` orchestrates parallel execution of bulk
operations (download, upload, etc.) across multiple items, handling
disk routing, job logging, retries, and UI event emission.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from internetarchive.bulk.disk import DiskPool
from internetarchive.bulk.jobs import JobLog
from internetarchive.bulk.ui.base import UIEvent
from internetarchive.bulk.worker import BaseWorker

logger = logging.getLogger(__name__)


class BulkEngine:
    """Orchestrates concurrent bulk operations on Archive.org items.

    Takes a list of identifiers, routes each to a destination
    directory with available disk space, executes worker operations
    in parallel via a thread pool, and logs progress to a
    :class:`~internetarchive.bulk.jobs.JobLog`.

    Args:
        worker: The worker implementation for the operation.
        job_log: Job log for resume semantics and event tracking.
        disk_pool: Disk pool for routing items to destination
            directories.
        num_workers: Number of concurrent worker threads.
        job_retries: Maximum number of retries for failed items.
        op: Operation name for log entries (e.g., ``"download"``).
        ui_handler: Optional callback for UI events. Called with
            a :class:`~internetarchive.bulk.ui.base.UIEvent` for
            each state transition.
    """

    def __init__(
        self,
        worker: BaseWorker,
        job_log: JobLog,
        disk_pool: DiskPool,
        num_workers: int = 1,
        job_retries: int = 0,
        op: str = "download",
        ui_handler: Callable[[UIEvent], None] | None = None,
    ) -> None:
        self._worker = worker
        self._job_log = job_log
        self._disk_pool = disk_pool
        self._num_workers = num_workers
        self._job_retries = job_retries
        self._op = op
        self._ui_handler = ui_handler

        # Counters (protected by _lock).
        self._lock = threading.Lock()
        self._completed = 0
        self._failed = 0
        self._skipped = 0
        self._total_bytes = 0

        # Worker ID mapping: thread ident → worker index.
        self._worker_ids: dict[int | None, int] = {}
        self._worker_id_lock = threading.Lock()
        self._next_worker_id = 0

        # Flow control.
        self._stop_requested = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially.

    # -- Public API ------------------------------------------------

    def run(self, identifiers: list[str]) -> dict:
        """Execute the bulk operation for all identifiers.

        Items already completed (per the job log) are skipped.
        Items that fail are retried up to ``job_retries`` times.

        Args:
            identifiers: List of Archive.org item identifiers.

        Returns:
            A dict with ``completed``, ``failed``, and ``skipped``
            counts.
        """
        total = len(identifiers)
        # Build queue: (identifier, retry_count, item_index).
        queue: list[tuple[str, int, int]] = []
        for idx, ident in enumerate(identifiers, start=1):
            if self._job_log.should_skip(ident):
                self._emit(UIEvent(
                    kind="item_skipped",
                    identifier=ident,
                    worker=0,
                    item_index=idx,
                ))
                with self._lock:
                    self._skipped += 1
                continue
            queue.append((ident, 0, idx))

        # Process the queue, including retries.
        self._process_queue(queue, total)

        with self._lock:
            return {
                "completed": self._completed,
                "failed": self._failed,
                "skipped": self._skipped,
            }

    def request_stop(self) -> None:
        """Signal the engine to stop submitting new items."""
        self._stop_requested.set()

    def pause(self) -> None:
        """Pause submission of new items (in-flight work continues)."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume item submission after a pause."""
        self._pause_event.set()

    # -- Internal --------------------------------------------------

    def _get_worker_id(self) -> int:
        """Map the current thread to a stable worker index (0..N-1)."""
        tid = threading.current_thread().ident
        with self._worker_id_lock:
            if tid not in self._worker_ids:
                self._worker_ids[tid] = self._next_worker_id
                self._next_worker_id += 1
            return self._worker_ids[tid]

    def _process_queue(
        self,
        queue: list[tuple[str, int, int]],
        total: int,
    ) -> None:
        """Submit items from *queue* to a thread pool.

        Size estimation and disk routing happen inside worker
        threads so the main thread can submit items rapidly
        without blocking on HTTP calls.
        """
        slots = threading.Semaphore(self._num_workers)

        retry_queue: list[tuple[str, int, int]] = []
        retry_lock = threading.Lock()

        with ThreadPoolExecutor(
            max_workers=self._num_workers,
        ) as pool:
            while queue:
                if self._stop_requested.is_set():
                    break

                futures: list[Future] = []

                for ident, retry, item_idx in queue:
                    if self._stop_requested.is_set():
                        break

                    self._pause_event.wait()

                    # Block until a worker slot is free.
                    slots.acquire()
                    if self._stop_requested.is_set():
                        slots.release()
                        break

                    fut = pool.submit(
                        self._run_item,
                        ident,
                        retry,
                        item_idx,
                        total,
                        slots,
                        retry_queue,
                        retry_lock,
                    )
                    futures.append(fut)

                # Wait for all in-flight futures to finish.
                for fut in futures:
                    fut.result()

                # Move retry queue into main queue for next pass.
                with retry_lock:
                    queue = list(retry_queue)
                    retry_queue.clear()

    def _run_item(
        self,
        identifier: str,
        retry: int,
        item_index: int,
        total: int,
        slots: threading.Semaphore,
        retry_queue: list[tuple[str, int, int]],
        retry_lock: threading.Lock,
    ) -> None:
        """Execute a single item in a worker thread.

        Handles size estimation, disk routing, execution, retry
        scheduling, and cleanup.  The semaphore slot is always
        released in the ``finally`` block.
        """
        worker_id = self._get_worker_id()
        destdir: str | None = None
        est_for_release = 0
        try:
            est = self._worker.estimate_size(identifier)
            destdir = self._disk_pool.route(est)

            if destdir is None:
                self._job_log.log_skipped(
                    identifier,
                    op=self._op,
                    reason="no_disk_space",
                )
                self._emit(UIEvent(
                    kind="item_skipped",
                    identifier=identifier,
                    worker=worker_id,
                    item_index=item_index,
                    error="no_disk_space",
                ))
                with self._lock:
                    self._skipped += 1
                return

            est_for_release = (
                est if est is not None else 2 * 1024**3
            )

            success = self._run_one(
                identifier,
                destdir,
                retry,
                item_index,
                total,
                worker_id,
                est,
            )
            if not success:
                retries_left = self._job_retries - retry - 1
                if retries_left >= 0:
                    with retry_lock:
                        retry_queue.append(
                            (identifier, retry + 1, item_index)
                        )
        finally:
            if destdir is not None:
                self._disk_pool.release(destdir, est_for_release)
            slots.release()

    def _run_one(
        self,
        identifier: str,
        destdir: str,
        retry: int,
        item_index: int,
        total: int,
        worker_id: int,
        est: int | None,
    ) -> bool:
        """Execute a single item operation in a worker thread.

        Returns ``True`` if the operation succeeded.
        """
        thread_name = threading.current_thread().name

        self._job_log.log_started(
            identifier,
            op=self._op,
            destdir=destdir,
            est_bytes=est if est is not None else 0,
            worker=thread_name,
            retry=retry,
        )
        self._emit(UIEvent(
            kind="item_started",
            identifier=identifier,
            worker=worker_id,
            item_index=item_index,
            bytes_total=est,
        ))

        t0 = time.monotonic()
        try:
            result = self._worker.execute(
                identifier, Path(destdir)
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            error_msg = str(exc)
            retries_left = self._job_retries - retry - 1
            self._job_log.log_failed(
                identifier,
                op=self._op,
                error=error_msg,
                retries_left=max(0, retries_left),
            )
            self._emit(UIEvent(
                kind="item_failed",
                identifier=identifier,
                worker=worker_id,
                item_index=item_index,
                error=error_msg,
                elapsed=elapsed,
            ))
            if retries_left < 0:
                with self._lock:
                    self._failed += 1
            return False

        elapsed = time.monotonic() - t0

        if result.success:
            self._job_log.log_completed(
                identifier,
                op=self._op,
                destdir=destdir,
                bytes_transferred=result.bytes_transferred,
                files_ok=result.files_ok,
                files_skipped=result.files_skipped,
                files_failed=result.files_failed,
                elapsed=elapsed,
            )
            self._emit(UIEvent(
                kind="item_completed",
                identifier=identifier,
                worker=worker_id,
                item_index=item_index,
                bytes_done=result.bytes_transferred,
                bytes_total=est,
                files_ok=result.files_ok,
                elapsed=elapsed,
            ))
            with self._lock:
                self._completed += 1
                self._total_bytes += result.bytes_transferred
            return True
        else:
            retries_left = self._job_retries - retry - 1
            self._job_log.log_failed(
                identifier,
                op=self._op,
                error=result.error or "unknown error",
                retries_left=max(0, retries_left),
            )
            self._emit(UIEvent(
                kind="item_failed",
                identifier=identifier,
                worker=worker_id,
                item_index=item_index,
                error=result.error,
                elapsed=elapsed,
            ))
            if retries_left < 0:
                with self._lock:
                    self._failed += 1
            return False

    def _emit(self, event: UIEvent) -> None:
        """Send a UIEvent to the registered handler, if any."""
        if self._ui_handler is not None:
            try:
                self._ui_handler(event)
            except Exception:
                logger.debug(
                    "UI handler raised an exception",
                    exc_info=True,
                )
