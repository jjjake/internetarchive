"""
internetarchive.bulk.ui
~~~~~~~~~~~~~~~~~~~~~~~~

Event system and UI handlers for bulk operations.

The engine emits ``UIEvent`` objects; handlers consume them.
``PlainUI`` writes timestamped lines to stderr. Future handlers
(Textual TUI, web UI) implement the same ``UIHandler`` ABC.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class UIEvent:
    """An event emitted by the bulk engine to the UI handler.

    :param kind: Event type (``job_started``, ``job_completed``,
        ``job_failed``, ``job_skipped``, ``backoff_start``,
        ``backoff_end``, ``progress``, ``file_started``,
        ``file_progress``, ``file_completed``).
    :param seq: Job sequence number (if applicable).
    :param total: Total number of jobs.
    :param identifier: Item identifier (if applicable).
    :param worker: Worker index (if applicable).
    :param error: Error message (for ``job_failed``).
    :param retry: Retry attempt number (for ``job_failed``).
    :param max_retries: Maximum retries configured.
    :param extra: Additional data from the worker result.
    :param elapsed: Elapsed time in seconds (for ``job_completed``).
    """

    kind: str
    seq: int = 0
    total: int = 0
    identifier: str = ""
    worker: int = 0
    error: str = ""
    retry: int = 0
    max_retries: int = 0
    extra: dict = field(default_factory=dict)
    elapsed: float = 0.0


class UIHandler(ABC):
    """Abstract base class for UI event handlers."""

    @abstractmethod
    def handle(self, event: UIEvent) -> None:
        """Handle a single UI event.

        :param event: The event to handle.
        """
        ...


class NullUI(UIHandler):
    """UI handler that silently discards all events."""

    def handle(self, event: UIEvent) -> None:
        """Discard the event.

        :param event: The event to discard.
        """


def _format_bytes(n: int) -> str:
    """Format byte count as human-readable string."""
    if n < 1024:
        return f"{n} B"
    value = float(n)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PB"


class PlainUI(UIHandler):
    """Timestamped plain-text UI handler writing to stderr.

    Output format::

        [03:12:01] [1/50000] foo-item: started (worker 2)
        [03:12:45] [1/50000] foo-item: completed (10.2 MB, 44s)
        [03:12:10] [2/50000] bar-item: failed: HTTP 503 (retry 1/3)
        [03:15:00] backoff: all disks full, waiting...
    """

    def __init__(self, file=None):
        self._file = file or sys.stderr

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    def _prefix(self, event: UIEvent) -> str:
        ts = self._ts()
        if event.seq and event.total:
            return f"[{ts}] [{event.seq}/{event.total}]"
        return f"[{ts}]"

    def handle(self, event: UIEvent) -> None:
        """Handle a UI event by printing to stderr.

        :param event: The event to handle.
        """
        prefix = self._prefix(event)

        if event.kind == "job_started":
            msg = (
                f"{prefix} {event.identifier}: "
                f"started (worker {event.worker})"
            )
        elif event.kind == "job_completed":
            parts = []
            if event.extra and event.extra.get("bytes"):
                parts.append(_format_bytes(event.extra["bytes"]))
            if event.elapsed:
                parts.append(f"{event.elapsed:.0f}s")
            detail = f" ({', '.join(parts)})" if parts else ""
            msg = (
                f"{prefix} {event.identifier}: "
                f"completed{detail}"
            )
        elif event.kind == "job_failed":
            retry_info = ""
            if event.retry and event.max_retries:
                retry_info = (
                    f" (retry {event.retry}/{event.max_retries})"
                )
            msg = (
                f"{prefix} {event.identifier}: "
                f"failed: {event.error}{retry_info}"
            )
        elif event.kind == "job_skipped":
            msg = (
                f"{prefix} {event.identifier}: "
                f"skipped (already completed)"
            )
        elif event.kind == "backoff_start":
            msg = f"{prefix} backoff: {event.error}"
        elif event.kind == "backoff_end":
            msg = f"{prefix} backoff: resuming"
        elif event.kind == "progress":
            msg = (
                f"{prefix} progress: "
                f"{event.extra.get('completed', 0)} completed, "
                f"{event.extra.get('failed', 0)} failed, "
                f"{event.extra.get('pending', 0)} pending"
            )
        else:
            msg = f"{prefix} {event.kind}: {event.identifier}"

        print(msg, file=self._file)


def _truncate(text: str, width: int) -> str:
    """Truncate *text* to *width* characters with an ellipsis."""
    if len(text) <= width:
        return text
    return text[: max(width - 1, 0)] + "\u2026"


class ProgressBarUI(UIHandler):
    """Multi-bar progress display using tqdm.

    Shows an overall item-count bar at position 0 and one
    per-worker bar (positions 1..N) that displays the file
    currently being downloaded with byte-level progress.

    :param total: Total number of jobs. If ``0``, the bar
        total is set lazily from the first event's ``.total``.
    :param initial: Number of already-finished jobs (for
        resume).
    :param max_workers: Number of concurrent download workers.
    :param file: Writable stream for the progress bars
        (default: ``sys.stderr``).
    """

    _DESC_WIDTH = 40

    def __init__(
        self,
        total: int = 0,
        initial: int = 0,
        max_workers: int = 4,
        file=None,
    ):
        from tqdm import tqdm  # noqa: PLC0415

        self._file = file or sys.stderr
        self._tqdm = tqdm
        self._total = total
        self._initial = initial
        self._max_workers = max_workers
        self._failed = 0
        self._total_bytes = 0

        # tqdm-stubs is incomplete — use Any for bar types.
        self._overall_bar: Any = None
        self._worker_bars: dict[int, Any] = {}
        self._pending_reset: dict[int, int] = {}
        self._lock = threading.Lock()

    # -- lazy creation ------------------------------------------------

    def _ensure_overall(self, total: int) -> None:
        """Lazily create the overall bar once total is known."""
        if self._overall_bar is not None:
            return
        self._overall_bar = self._tqdm(  # type: ignore[call-arg]
            total=total,
            initial=self._initial,
            desc="Batch",
            unit="item",
            position=0,
            file=self._file,
            dynamic_ncols=True,
        )

    def _get_worker_bar(self, idx: int) -> Any:
        """Get or create the tqdm bar for worker *idx*.

        :param idx: Zero-based worker index.
        :returns: A ``tqdm`` progress bar instance.
        """
        if idx not in self._worker_bars:
            bar: Any = self._tqdm(  # type: ignore[call-arg]
                total=0,
                desc=f"W{idx} (idle)",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                position=idx + 1,
                file=self._file,
                dynamic_ncols=True,
                leave=True,
            )
            self._worker_bars[idx] = bar
        return self._worker_bars[idx]

    # -- postfix helper -----------------------------------------------

    def _refresh_overall_postfix(self) -> None:
        """Update the overall bar postfix with byte totals."""
        if self._overall_bar is None:
            return
        parts: dict[str, Any] = {}
        if self._total_bytes:
            parts["dl"] = _format_bytes(self._total_bytes)
        if self._failed:
            parts["fail"] = self._failed
        if parts:
            self._overall_bar.set_postfix(
                **parts, refresh=False
            )

    # -- event dispatch -----------------------------------------------

    def handle(self, event: UIEvent) -> None:
        """Handle a UI event by updating progress bars.

        :param event: The event to handle.
        """
        with self._lock:
            self._handle(event)

    def _handle(self, event: UIEvent) -> None:
        """Dispatch a single event (called under lock).

        :param event: The event to dispatch.
        """
        total = self._total or event.total
        if total:
            self._ensure_overall(total)

        kind = event.kind

        if kind == "job_started":
            bar = self._get_worker_bar(event.worker)
            desc = _truncate(
                f"W{event.worker} {event.identifier}",
                self._DESC_WIDTH,
            )
            bar.reset(total=0)
            bar.set_description(desc)

        elif kind == "file_started":
            bar = self._get_worker_bar(event.worker)
            fname = event.extra.get("file_name", "")
            fsize = event.extra.get("file_size", 0)
            desc = _truncate(
                f"W{event.worker} "
                f"{event.identifier}/{fname}",
                self._DESC_WIDTH,
            )
            # Defer the bar reset until the first
            # file_progress event so the previous file's
            # 100% stays visible between files.
            self._pending_reset[event.worker] = fsize
            bar.set_description(desc)

        elif kind == "file_progress":
            bar = self._get_worker_bar(event.worker)
            if event.worker in self._pending_reset:
                new_total = self._pending_reset.pop(
                    event.worker
                )
                bar.reset(total=new_total)
            nbytes = event.extra.get("bytes", 0)
            bar.update(nbytes)
            self._total_bytes += nbytes
            self._refresh_overall_postfix()

        elif kind == "file_completed":
            bar = self._get_worker_bar(event.worker)
            if event.worker in self._pending_reset:
                # No progress events (file was skipped).
                fsize = self._pending_reset.pop(
                    event.worker
                )
                bar.reset(total=fsize)
            if bar.total:
                bar.n = bar.total
                bar.refresh()

        elif kind == "job_completed":
            if self._overall_bar is not None:
                self._refresh_overall_postfix()
                self._overall_bar.update(1)
            bar = self._get_worker_bar(event.worker)
            bar.reset(total=0)
            bar.set_description(
                f"W{event.worker} (idle)"
            )

        elif kind == "job_failed":
            if not event.retry:
                self._failed += 1
                if self._overall_bar is not None:
                    self._refresh_overall_postfix()
                    self._overall_bar.update(1)
            bar = self._get_worker_bar(event.worker)
            bar.reset(total=0)
            bar.set_description(
                f"W{event.worker} (idle)"
            )

        elif kind == "job_skipped":
            if self._overall_bar is not None:
                self._overall_bar.update(1)

        elif kind == "backoff_start":
            if self._overall_bar is not None:
                self._overall_bar.set_description(
                    "backoff"
                )

        elif kind == "backoff_end":
            if self._overall_bar is not None:
                self._overall_bar.set_description("Batch")

        elif kind == "progress":
            self.close()

    # -- cleanup ------------------------------------------------------

    def close(self) -> None:
        """Close all tqdm bars."""
        for bar in self._worker_bars.values():
            bar.close()
        self._worker_bars.clear()
        if self._overall_bar is not None:
            self._overall_bar.close()
            self._overall_bar = None
