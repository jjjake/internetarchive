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
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# -- ANSI constants (gated on isatty at runtime) ----------------------

_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"
_SYM_ACTIVE = "\u25cf"  # bullet
_SYM_DONE = "\u2713"  # check
_SYM_FAIL = "\u2717"  # cross
_ARROW = "\u2192"  # right arrow


@dataclass
class UIEvent:
    """An event emitted by the bulk engine to the UI handler.

    :param kind: Event type (``job_started``, ``job_routed``,
        ``job_completed``, ``job_failed``, ``job_skipped``,
        ``backoff_start``, ``backoff_end``, ``progress``,
        ``file_started``, ``file_progress``, ``file_completed``,
        ``shutdown``).
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

        [03:12:01] [1/50000] foo-item: started
        [03:12:02] [1/50000] foo-item: \u2192 /mnt/disk1
        [03:12:45] [1/50000] foo-item: completed (10.2 MB, 44s)
        [03:12:10] [2/50000] bar-item: failed: HTTP 503 (retry 1/3)
        [03:15:00] backoff: all disks full, waiting...
        [03:15:30] shutting down gracefully...
    """

    def __init__(self, file=None):
        self._file = file or sys.stderr

    def _ts(self) -> str:
        """Return a UTC timestamp string."""
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    def _prefix(self, event: UIEvent) -> str:
        """Build a prefix with timestamp and optional seq/total."""
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
            msg = f"{prefix} {event.identifier}: started"
        elif event.kind == "job_routed":
            destdir = event.extra.get("destdir", ".")
            msg = (
                f"{prefix} {event.identifier}: "
                f"{_ARROW} {destdir}"
            )
        elif event.kind == "job_completed":
            parts = []
            nbytes = (
                event.extra.get("bytes", 0) if event.extra
                else 0
            )
            if nbytes:
                parts.append(_format_bytes(nbytes))
            if event.elapsed:
                parts.append(f"{event.elapsed:.0f}s")
            if nbytes and event.elapsed > 0:
                speed = nbytes / event.elapsed
                parts.append(f"{_format_bytes(int(speed))}/s")
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
        elif event.kind == "shutdown":
            msg = f"{prefix} shutting down gracefully..."
        else:
            msg = f"{prefix} {event.kind}: {event.identifier}"

        print(msg, file=self._file)


def _visible_len(text: str) -> int:
    """Return the visible length of *text*, ignoring ANSI escapes."""
    import re  # noqa: PLC0415
    return len(re.sub(r"\033\[[0-9;]*m", "", text))


def _truncate(text: str, width: int) -> str:
    """Truncate *text* to *width* visible characters with an ellipsis.

    ANSI escape sequences are not counted toward the width.
    """
    if _visible_len(text) <= width:
        return text
    import re  # noqa: PLC0415
    visible = 0
    i = 0
    while i < len(text) and visible < width - 1:
        m = re.match(r"\033\[[0-9;]*m", text[i:])
        if m:
            i += m.end()
        else:
            visible += 1
            i += 1
    reset = _RESET if "\033[" in text[:i] else ""
    return text[:i] + reset + "\u2026"


class ProgressBarUI(UIHandler):
    """Multi-bar progress display using tqdm.

    Shows an overall item-count bar at position 0 and two bars
    per worker: a header bar (desc-only, showing identifier and
    destination directory) and a progress bar (byte-level file
    progress).

    :param total: Total number of jobs. If ``0``, the bar
        total is set lazily from the first event's ``.total``.
    :param initial: Number of already-finished jobs (for
        resume).
    :param max_workers: Number of concurrent download workers.
    :param file: Writable stream for the progress bars
        (default: ``sys.stderr``).
    """

    _DESC_WIDTH = 50

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
        self._use_color = getattr(
            self._file, "isatty", lambda: False
        )()

        # tqdm-stubs is incomplete — use Any for bar types.
        self._overall_bar: Any = None
        self._header_bars: dict[int, Any] = {}
        self._progress_bars: dict[int, Any] = {}
        self._pending_reset: dict[int, int] = {}
        self._worker_state: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._saved_termios: list | None = None
        self._start_time: float = time.monotonic()
        self._last_overall_refresh: float = 0.0

    # -- ANSI helpers -------------------------------------------------

    def _ansi(self, code: str, text: str) -> str:
        """Wrap *text* in an ANSI escape sequence if color enabled.

        :param code: ANSI escape code (e.g. ``_BOLD``).
        :param text: Text to wrap.
        :returns: Wrapped or plain text.
        """
        if not self._use_color:
            return text
        return f"{code}{text}{_RESET}"

    # -- lazy creation ------------------------------------------------

    def _suppress_echo(self) -> None:
        """Disable terminal echo to prevent keypresses from
        disrupting the multi-bar tqdm display.
        """
        if not self._use_color:
            return
        try:
            import termios  # noqa: PLC0415
            fd = sys.stdin.fileno()
            self._saved_termios = termios.tcgetattr(fd)
            new = termios.tcgetattr(fd)
            new[3] = new[3] & ~termios.ECHO
            termios.tcsetattr(
                fd, termios.TCSADRAIN, new
            )
        except (ImportError, OSError):
            pass

    def _restore_echo(self) -> None:
        """Restore terminal echo settings saved by
        ``_suppress_echo()``.
        """
        if self._saved_termios is None:
            return
        try:
            import termios  # noqa: PLC0415
            termios.tcsetattr(
                sys.stdin.fileno(),
                termios.TCSADRAIN,
                self._saved_termios,
            )
        except (ImportError, OSError):
            pass
        self._saved_termios = None

    def _ensure_overall(self, total: int) -> None:
        """Lazily create the overall bar once total is known."""
        if self._overall_bar is not None:
            return
        self._suppress_echo()
        colour = "green" if self._use_color else None
        self._overall_bar = self._tqdm(  # type: ignore[call-arg]
            total=total,
            initial=self._initial,
            desc="Batch",
            unit="item",
            ascii=" -",
            colour=colour,
            bar_format=(
                "{desc} {percentage:3.0f}% "
                "{bar} "
                "{n_fmt}/{total_fmt} "
                "[{elapsed}<{remaining}]"
                "{postfix}"
            ),
            position=0,
            file=self._file,
            dynamic_ncols=True,
        )

    def _get_header_bar(self, idx: int) -> Any:
        """Get or create the header bar for worker *idx*.

        Header bars are desc-only (no meter) and show the
        identifier and destination directory.

        :param idx: Zero-based worker index.
        :returns: A ``tqdm`` progress bar instance.
        """
        if idx not in self._header_bars:
            bar: Any = self._tqdm(  # type: ignore[call-arg]
                total=0,
                bar_format="{desc}",
                position=1 + idx * 2,
                file=self._file,
                dynamic_ncols=True,
                leave=True,
            )
            self._header_bars[idx] = bar
        return self._header_bars[idx]

    def _get_progress_bar(self, idx: int) -> Any:
        """Get or create the progress bar for worker *idx*.

        Progress bars show byte-level download progress for the
        current file.

        :param idx: Zero-based worker index.
        :returns: A ``tqdm`` progress bar instance.
        """
        if idx not in self._progress_bars:
            if self._use_color:
                d = _DIM
                r = _RESET
                bfmt = (
                    f"{{desc}} {d}{{bar}}{r} "
                    f"{d}{{n_fmt}}/{{total_fmt}}{r}"
                )
            else:
                bfmt = (
                    "{desc} "
                    "{bar} "
                    "{n_fmt}/{total_fmt}"
                )
            colour = "green" if self._use_color else None
            bar: Any = self._tqdm(  # type: ignore[call-arg]
                total=0,
                desc="",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                ascii=" -",
                colour=colour,
                bar_format=bfmt,
                position=2 + idx * 2,
                file=self._file,
                dynamic_ncols=True,
                leave=True,
            )
            self._progress_bars[idx] = bar
        return self._progress_bars[idx]

    # -- header description helpers -----------------------------------

    def _header_active(
        self, identifier: str, destdir: str | None = None
    ) -> str:
        """Build the header description for an active job.

        Green bullet, bold identifier, dim destination.

        :param identifier: Item identifier.
        :param destdir: Destination directory (or ``None``).
        :returns: Formatted header string.
        """
        sym = self._ansi(_GREEN, _SYM_ACTIVE)
        ident = self._ansi(_BOLD, identifier)
        if destdir:
            path = self._ansi(_DIM, f"{_ARROW} {destdir}")
            text = f"{sym} {ident} {path}"
        else:
            text = f"{sym} {ident}"
        return _truncate(text, self._DESC_WIDTH)

    def _header_done(
        self, identifier: str, destdir: str | None = None
    ) -> str:
        """Build the header description for a completed job.

        Dim green checkmark, everything else dimmed.

        :param identifier: Item identifier.
        :param destdir: Destination directory (or ``None``).
        :returns: Formatted header string.
        """
        sym = self._ansi(f"{_DIM}{_GREEN}", _SYM_DONE)
        if destdir:
            rest = f"{identifier} {_ARROW} {destdir}"
        else:
            rest = identifier
        text = f"{sym} {self._ansi(_DIM, rest)}"
        return _truncate(text, self._DESC_WIDTH)

    def _header_failed(
        self, identifier: str, destdir: str | None = None
    ) -> str:
        """Build the header description for a failed job.

        Red cross, bold identifier, dim destination.

        :param identifier: Item identifier.
        :param destdir: Destination directory (or ``None``).
        :returns: Formatted header string.
        """
        sym = self._ansi(_RED, _SYM_FAIL)
        ident = self._ansi(_BOLD, identifier)
        if destdir:
            path = self._ansi(_DIM, f"{_ARROW} {destdir}")
            text = f"{sym} {ident} {path}"
        else:
            text = f"{sym} {ident}"
        return _truncate(text, self._DESC_WIDTH)

    # -- postfix helper -----------------------------------------------

    def _refresh_overall_postfix(self) -> None:
        """Update the overall bar postfix with byte totals
        and aggregate throughput.

        Uses a 1-second throttle to avoid excessive
        terminal I/O from high-frequency chunk events.
        """
        if self._overall_bar is None:
            return
        now = time.monotonic()
        if now - self._last_overall_refresh < 1.0:
            return
        self._last_overall_refresh = now
        parts: dict[str, Any] = {}
        if self._total_bytes:
            parts["dl"] = _format_bytes(self._total_bytes)
            elapsed = now - self._start_time
            if elapsed > 0:
                speed = self._total_bytes / elapsed
                parts["speed"] = (
                    f"{_format_bytes(int(speed))}/s"
                )
        if self._failed:
            parts["fail"] = self._failed
        if parts:
            self._overall_bar.set_postfix(**parts)
        else:
            self._overall_bar.refresh()

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
            self._worker_state[event.worker] = {
                "identifier": event.identifier,
                "destdir": None,
            }
            hbar = self._get_header_bar(event.worker)
            hbar.set_description_str(
                self._header_active(event.identifier)
            )
            pbar = self._get_progress_bar(event.worker)
            pbar.reset(total=0)
            pbar.set_description(
                self._ansi(_DIM, "  (waiting...)")
            )

        elif kind == "job_routed":
            destdir = event.extra.get("destdir", ".")
            state = self._worker_state.get(event.worker)
            if state is not None:
                state["destdir"] = destdir
            hbar = self._get_header_bar(event.worker)
            hbar.set_description_str(
                self._header_active(
                    event.identifier, destdir
                )
            )

        elif kind == "file_started":
            pbar = self._get_progress_bar(event.worker)
            fname = event.extra.get("file_name", "")
            fsize = event.extra.get("file_size", 0)
            desc = self._ansi(
                _DIM,
                _truncate(f"  {fname}", self._DESC_WIDTH),
            )
            # Defer the bar reset until the first
            # file_progress event so the previous file's
            # 100% stays visible between files.
            self._pending_reset[event.worker] = fsize
            pbar.set_description(desc)

        elif kind == "file_progress":
            pbar = self._get_progress_bar(event.worker)
            if event.worker in self._pending_reset:
                new_total = self._pending_reset.pop(
                    event.worker
                )
                pbar.reset(total=new_total)
            nbytes = event.extra.get("bytes", 0)
            pbar.update(nbytes)
            self._total_bytes += nbytes
            self._refresh_overall_postfix()

        elif kind == "file_completed":
            pbar = self._get_progress_bar(event.worker)
            if event.worker in self._pending_reset:
                # No progress events (file was skipped).
                fsize = self._pending_reset.pop(
                    event.worker
                )
                pbar.reset(total=fsize)
            if pbar.total:
                pbar.n = pbar.total
                pbar.refresh()

        elif kind == "job_completed":
            if self._overall_bar is not None:
                self._refresh_overall_postfix()
                self._overall_bar.update(1)
            state = self._worker_state.get(event.worker, {})
            destdir = state.get("destdir")
            hbar = self._get_header_bar(event.worker)
            hbar.set_description_str(
                self._header_done(
                    event.identifier, destdir
                )
            )
            pbar = self._get_progress_bar(event.worker)
            pbar.reset(total=0)
            pbar.set_description("")

        elif kind == "job_failed":
            if not event.retry:
                self._failed += 1
                if self._overall_bar is not None:
                    self._refresh_overall_postfix()
                    self._overall_bar.update(1)
            state = self._worker_state.get(event.worker, {})
            destdir = state.get("destdir")
            hbar = self._get_header_bar(event.worker)
            hbar.set_description_str(
                self._header_failed(
                    event.identifier, destdir
                )
            )
            pbar = self._get_progress_bar(event.worker)
            pbar.reset(total=0)
            pbar.set_description("")

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

        elif kind == "shutdown":
            if self._overall_bar is not None:
                self._overall_bar.set_description(
                    "Shutting down..."
                )

        elif kind == "progress":
            self.close()

    # -- cleanup ------------------------------------------------------

    def close(self) -> None:
        """Close all tqdm bars and restore terminal settings."""
        for bar in self._header_bars.values():
            bar.close()
        self._header_bars.clear()
        for bar in self._progress_bars.values():
            bar.close()
        self._progress_bars.clear()
        if self._overall_bar is not None:
            self._overall_bar.close()
            self._overall_bar = None
        self._restore_echo()
