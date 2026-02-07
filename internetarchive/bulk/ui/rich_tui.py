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
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.

"""
internetarchive.bulk.ui.rich_tui
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rich-based live TUI for bulk operations.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import time

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False

from internetarchive.bulk.ui.base import UIEvent
from internetarchive.bulk.ui.tui import TUIState, _format_bytes

# Status symbols and styles for recent-item display.
_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "completed": ("+", "green"),
    "failed": ("X", "red bold"),
    "skipped": ("o", "yellow"),
}


def _format_elapsed(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


class RichTUI:
    """Rich-based live TUI for bulk operations.

    Uses :class:`TUIState` from the curses TUI for state tracking
    so that both backends share identical event-handling logic.

    Args:
        num_workers: Number of concurrent download workers.
        total_items: Total number of items to process, or
            ``None`` if the total is unknown.
    """

    def __init__(
        self,
        num_workers: int,
        total_items: int | None = None,
    ) -> None:
        if not HAS_RICH:
            raise ImportError(
                "rich is required for RichTUI. "
                "Install with: pip install internetarchive[ui]"
            )
        self._state = TUIState(num_workers, total_items)
        self._console = Console(stderr=True)
        self._live: Live | None = None

    # -- lifecycle ---------------------------------------------------

    def start(self) -> None:
        """Start the Rich Live display."""
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the Rich Live display."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    def handle_event(self, event: UIEvent) -> None:
        """Update state and refresh the live display."""
        self._state.handle_event(event)
        if self._live is not None:
            self._live.update(self._render())

    # -- rendering ---------------------------------------------------

    def _render(self) -> Table:
        """Build a Rich Table showing status and workers."""
        s = self._state

        table = Table(
            show_header=False,
            show_edge=False,
            pad_edge=False,
            expand=True,
        )
        table.add_column(ratio=1)

        # -- summary row ---------------------------------------------
        table.add_row(self._render_summary(s))
        table.add_row("")  # blank separator

        # -- worker rows ---------------------------------------------
        for wid in range(s.num_workers):
            table.add_row(self._render_worker(s, wid))

        # -- recent items --------------------------------------------
        recent = list(s.recent)[-6:]
        if recent:
            table.add_row("")  # blank separator
            table.add_row(
                Text("Recent:", style="bold underline"),
            )
            for entry in recent:
                table.add_row(self._render_recent(entry))

        return table

    @staticmethod
    def _render_summary(s: TUIState) -> Text:
        """Build the summary line."""
        parts: list[str] = []

        if s.total_items is not None:
            done = s.completed + s.failed + s.skipped
            parts.append(f"Items: {done}/{s.total_items}")
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

        elapsed = time.time() - s.start_time
        parts.append(f"Elapsed: {_format_elapsed(elapsed)}")

        if s.total_bytes and elapsed > 0:
            rate = s.total_bytes / elapsed
            parts.append(f"{_format_bytes(int(rate))}/s")

        return Text("  ".join(parts), style="bold")

    @staticmethod
    def _render_worker(s: TUIState, wid: int) -> Text:
        """Render a single worker row."""
        info = s.active_workers.get(wid)
        if info is None:
            return Text(f"  W{wid}: idle", style="dim")

        ident = info["identifier"]
        total = info.get("bytes_total", 0) or 0
        started_at = info.get("started_at")

        text = f"  W{wid}: {ident}"

        if total > 0:
            text += f"  ({_format_bytes(total)})"

        if started_at is not None:
            elapsed = time.time() - started_at
            text += f"  {_format_elapsed(elapsed)}"

        return Text(text, style="cyan")

    @staticmethod
    def _render_recent(entry: dict) -> Text:
        """Render a single recent-item row."""
        status = entry.get("status", "")
        sym, style = _STATUS_STYLES.get(status, ("?", ""))
        ident = entry.get("identifier", "???")

        parts = [f"  {sym} {ident}"]

        if status == "failed":
            err = entry.get("error", "")
            if err:
                parts.append(f"({err})")
        elif status == "completed":
            bt = entry.get("bytes_total")
            if bt is not None:
                parts.append(_format_bytes(bt))
            el = entry.get("elapsed")
            if el is not None:
                parts.append(f"{el:.1f}s")
            fok = entry.get("files_ok")
            if fok is not None:
                parts.append(
                    f"{fok} file{'s' if fok != 1 else ''}"
                )

        return Text("  ".join(parts), style=style)
