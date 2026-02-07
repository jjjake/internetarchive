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
internetarchive.bulk.ui.tui
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Curses-based TUI for bulk operations.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import curses
import queue
import threading
import time
from collections import deque

from internetarchive.bulk.ui.base import UIEvent


def _format_bytes(n: int) -> str:
    """Format a byte count as a human-readable string.

    Examples::

        >>> _format_bytes(0)
        '0 B'
        >>> _format_bytes(1024)
        '1.0 KB'
        >>> _format_bytes(1_073_741_824)
        '1.0 GB'
    """
    if n < 1024:
        return f"{n} B"
    value = float(n)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
    # Unreachable, but satisfies type checkers.
    return f"{n} B"  # pragma: no cover


class TUIState:
    """Pure data class that tracks UI state for the curses TUI.

    This class contains no rendering logic and can be tested
    without any curses dependency.

    Args:
        num_workers: Number of concurrent download workers.
        total_items: Total number of items to process, or None
            if the total is unknown.
    """

    def __init__(
        self,
        num_workers: int,
        total_items: int | None = None,
    ) -> None:
        self.num_workers = num_workers
        self.total_items = total_items
        self.completed: int = 0
        self.failed: int = 0
        self.skipped: int = 0
        self.total_bytes: int = 0
        self.active_workers: dict[int, dict] = {}
        self.recent: deque[dict] = deque(maxlen=10)
        self.start_time: float = time.time()

    def handle_event(self, event: UIEvent) -> None:
        """Dispatch an event to the appropriate handler.

        Looks up a method named ``_on_{event.kind}``; if none
        exists the event is silently ignored so that new event
        kinds do not break the TUI.
        """
        handler = getattr(self, f"_on_{event.kind}", None)
        if handler is not None:
            handler(event)

    # -- individual event handlers -----------------------------------------

    def _on_item_started(self, event: UIEvent) -> None:
        """Record a new active worker."""
        self.active_workers[event.worker] = {
            "identifier": event.identifier,
            "item_index": event.item_index,
            "bytes_total": event.bytes_total,
            "bytes_done": 0,
            "filename": None,
            "started_at": time.time(),
        }

    def _on_item_completed(self, event: UIEvent) -> None:
        """Mark an item as completed."""
        self.completed += 1
        if event.bytes_total is not None:
            self.total_bytes += event.bytes_total
        self.active_workers.pop(event.worker, None)
        self.recent.append({
            "identifier": event.identifier,
            "status": "completed",
            "bytes_total": event.bytes_total,
            "elapsed": event.elapsed,
            "files_ok": event.files_ok,
        })

    def _on_item_failed(self, event: UIEvent) -> None:
        """Mark an item as failed."""
        self.failed += 1
        self.active_workers.pop(event.worker, None)
        self.recent.append({
            "identifier": event.identifier,
            "status": "failed",
            "error": event.error,
        })

    def _on_item_skipped(self, event: UIEvent) -> None:
        """Mark an item as skipped."""
        self.skipped += 1
        self.recent.append({
            "identifier": event.identifier,
            "status": "skipped",
        })

    def _on_file_progress(self, event: UIEvent) -> None:
        """Update progress for an active worker."""
        worker = self.active_workers.get(event.worker)
        if worker is not None:
            worker["filename"] = event.filename
            worker["bytes_done"] = event.bytes_done or 0
            worker["bytes_total"] = event.bytes_total or 0


# -- Status symbols for recent items ------------------------------------

_STATUS_SYMBOLS: dict[str, str] = {
    "completed": "+",
    "failed": "X",
    "skipped": "o",
}


class CursesTUI:
    """Curses-based TUI that renders download progress.

    The TUI runs a rendering loop in a dedicated thread so that
    it does not block the main download pipeline.  Events are
    passed in via :meth:`handle_event`, which updates the shared
    :class:`TUIState` and enqueues a render request.

    Args:
        num_workers: Number of concurrent download workers.
        total_items: Total number of items to process, or None
            if the total is unknown.
    """

    # Render interval in seconds.
    _RENDER_HZ: float = 0.1

    def __init__(
        self,
        num_workers: int,
        total_items: int | None = None,
    ) -> None:
        self._state = TUIState(num_workers, total_items)
        self._queue: queue.Queue[UIEvent | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._stdscr: curses.window | None = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Start the render thread and initialize curses."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="curses-tui",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the render thread to stop and wait for it."""
        self._running = False
        # Send a sentinel so the thread wakes up from queue.get().
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def handle_event(self, event: UIEvent) -> None:
        """Update state and enqueue a render request."""
        self._state.handle_event(event)
        self._queue.put(event)

    # -- thread entry point ------------------------------------------------

    def _run(self) -> None:
        """Entry point for the render thread."""
        try:
            curses.wrapper(self._main_loop)
        except Exception:  # noqa: S110
            # If curses fails (e.g. no terminal), silently degrade.
            pass

    def _main_loop(self, stdscr: curses.window) -> None:
        """Main curses loop: drain events, render periodically."""
        self._stdscr = stdscr
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(int(self._RENDER_HZ * 1000))

        while self._running:
            # Drain all pending events without blocking.
            self._drain_queue()
            self._render(stdscr)
            # Brief sleep to avoid busy-looping.
            time.sleep(self._RENDER_HZ)

        # Final render before exit.
        self._drain_queue()
        self._render(stdscr)

    def _drain_queue(self) -> None:
        """Process all pending events in the queue."""
        while True:
            try:
                event = self._queue.get_nowait()
                if event is None:
                    # Sentinel: stop signal, don't process.
                    continue
                # State was already updated in handle_event();
                # this drain is just to clear the queue.
            except queue.Empty:
                break

    # -- rendering ---------------------------------------------------------

    def _render(self, stdscr: curses.window) -> None:
        """Redraw the full TUI screen."""
        try:
            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()
            row = 0

            # -- header ---------------------------------------------------
            row = self._render_header(stdscr, row, max_x)
            row += 1  # blank line

            # -- worker rows ----------------------------------------------
            row = self._render_workers(stdscr, row, max_x)
            row += 1  # blank line

            # -- recent ---------------------------------------------------
            self._render_recent(stdscr, row, max_x, max_y)

            stdscr.refresh()
        except curses.error:
            # Terminal too small or other curses issue; skip frame.
            pass

    def _render_header(
        self, stdscr: curses.window, row: int, max_x: int
    ) -> int:
        """Render the header line with summary counts."""
        s = self._state
        parts: list[str] = []

        if s.total_items is not None:
            parts.append(
                f"Items: {s.completed}/{s.total_items}"
            )
        else:
            parts.append(f"Completed: {s.completed}")

        active = len(s.active_workers)
        parts.append(f"Active: {active}")

        if s.failed:
            parts.append(f"Failed: {s.failed}")
        if s.skipped:
            parts.append(f"Skipped: {s.skipped}")
        if s.total_bytes:
            parts.append(_format_bytes(s.total_bytes))

        header = "  ".join(parts)
        self._addstr(stdscr, row, 0, header[:max_x - 1])
        return row + 1

    def _render_workers(
        self, stdscr: curses.window, row: int, max_x: int
    ) -> int:
        """Render one row per worker."""
        s = self._state
        for wid in range(s.num_workers):
            if row >= curses.LINES - 1:
                break
            info = s.active_workers.get(wid)
            if info is None:
                line = f"  W{wid}: idle"
            else:
                ident = info["identifier"]
                fname = info.get("filename") or ""
                done = info.get("bytes_done", 0) or 0
                total = info.get("bytes_total", 0) or 0

                # Build progress bar.
                bar = self._progress_bar(done, total, width=20)
                if total > 0:
                    pct = done / total * 100
                    pct_str = f"{pct:5.1f}%"
                else:
                    pct_str = "     "

                # Truncate filename if needed.
                if fname and len(fname) > 20:
                    fname = "..." + fname[-17:]

                line = (
                    f"  W{wid}: {ident}  "
                    f"{fname}  {bar} {pct_str}"
                )

            self._addstr(
                stdscr, row, 0, line[:max_x - 1]
            )
            row += 1
        return row

    def _render_recent(
        self,
        stdscr: curses.window,
        row: int,
        max_x: int,
        max_y: int,
    ) -> None:
        """Render the last few completed/failed/skipped items."""
        s = self._state
        # Show up to 4 most recent items.
        items = list(s.recent)[-4:]
        if not items:
            return

        self._addstr(stdscr, row, 0, "Recent:")
        row += 1

        for entry in items:
            if row >= max_y - 1:
                break
            sym = _STATUS_SYMBOLS.get(
                entry.get("status", ""), "?"
            )
            ident = entry.get("identifier", "???")
            detail = ""
            if entry.get("status") == "failed":
                err = entry.get("error", "")
                if err:
                    detail = f" ({err})"
            elif entry.get("status") == "completed":
                bt = entry.get("bytes_total")
                if bt is not None:
                    detail = f" {_format_bytes(bt)}"

            line = f"  {sym} {ident}{detail}"
            self._addstr(
                stdscr, row, 0, line[:max_x - 1]
            )
            row += 1

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _progress_bar(
        done: int, total: int, width: int = 20
    ) -> str:
        """Build an ASCII progress bar like ``[=========>    ]``."""
        if total <= 0:
            return "[" + " " * width + "]"
        filled = int(width * done / total)
        filled = min(filled, width)
        empty = width - filled
        bar_body = "=" * filled
        if filled < width:
            bar_body = bar_body[:-1] + ">" if filled else ""
            empty = width - len(bar_body)
        return "[" + bar_body + " " * empty + "]"

    @staticmethod
    def _addstr(
        stdscr: curses.window,
        y: int,
        x: int,
        text: str,
    ) -> None:
        """Safe wrapper around ``addstr`` that ignores errors."""
        try:
            stdscr.addstr(y, x, text)
        except curses.error:
            pass
