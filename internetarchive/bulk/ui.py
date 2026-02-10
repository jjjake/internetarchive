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
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UIEvent:
    """An event emitted by the bulk engine to the UI handler.

    :param kind: Event type (``job_started``, ``job_completed``,
        ``job_failed``, ``job_skipped``, ``backoff_start``,
        ``backoff_end``, ``progress``).
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
