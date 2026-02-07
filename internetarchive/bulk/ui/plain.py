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
internetarchive.bulk.ui.plain
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Plain-text UI for bulk operations.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import IO

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


class PlainUI:
    """Plain-text UI that writes timestamped status lines to a stream.

    Output format::

        [HH:MM:SS] [idx/total] identifier: message

    Args:
        stream: Writable text stream (defaults to sys.stderr).
        total_items: Total number of items to process (used for progress display).
        num_workers: Number of concurrent workers.
    """

    def __init__(
        self,
        stream: IO[str] | None = None,
        total_items: int | None = None,
        num_workers: int = 1,
    ) -> None:
        self.stream: IO[str] = stream if stream is not None else sys.stderr
        self.total_items = total_items
        self.num_workers = num_workers

    def handle_event(self, event: UIEvent) -> None:
        """Dispatch an event to the appropriate handler.

        Looks up a method named ``_on_{event.kind}``; if none exists the
        event is silently ignored so that new event kinds do not break
        older UI implementations.
        """
        handler = getattr(self, f"_on_{event.kind}", None)
        if handler is not None:
            handler(event)

    # -- individual event handlers ------------------------------------------

    def _on_item_started(self, event: UIEvent) -> None:
        self._write(event, "download started")

    def _on_item_completed(self, event: UIEvent) -> None:
        parts: list[str] = ["completed"]
        if event.files_ok is not None:
            parts.append(f"{event.files_ok} files")
        if event.bytes_done is not None:
            parts.append(_format_bytes(event.bytes_done))
        if event.elapsed is not None:
            parts.append(f"{event.elapsed:.1f}s")
        self._write(event, ", ".join(parts))

    def _on_item_failed(self, event: UIEvent) -> None:
        msg = "FAILED"
        if event.error:
            msg = f"FAILED: {event.error}"
        self._write(event, msg)

    def _on_item_skipped(self, event: UIEvent) -> None:
        self._write(event, "skipped (already complete)")

    def _on_file_progress(self, event: UIEvent) -> None:
        parts: list[str] = []
        if event.filename:
            parts.append(event.filename)
        if event.bytes_done is not None and event.bytes_total:
            pct = event.bytes_done / event.bytes_total * 100
            parts.append(
                f"{_format_bytes(event.bytes_done)}"
                f"/{_format_bytes(event.bytes_total)}"
                f" ({pct:.0f}%)"
            )
        self._write(event, " ".join(parts) if parts else "file progress")

    def _on_disk_update(self, event: UIEvent) -> None:
        parts: list[str] = ["disk"]
        if event.bytes_done is not None and event.bytes_total is not None:
            parts.append(
                f"{_format_bytes(event.bytes_done)}"
                f"/{_format_bytes(event.bytes_total)}"
            )
        self._write(event, " ".join(parts))

    # -- summary ------------------------------------------------------------

    def print_summary(
        self,
        completed: int,
        failed: int,
        skipped: int,
        total_bytes: int,
        elapsed: float,
    ) -> None:
        """Print a final summary line after all items have been processed."""
        summary = (
            f"Summary: {completed} completed, {failed} failed, "
            f"{skipped} skipped, {_format_bytes(total_bytes)} "
            f"in {elapsed:.1f}s"
        )
        ts = self._timestamp()
        self.stream.write(f"[{ts}] {summary}\n")
        self.stream.flush()

    # -- helpers ------------------------------------------------------------

    def _progress_tag(self, event: UIEvent) -> str:
        """Build the ``[idx/total]`` tag from an event."""
        idx = event.item_index
        if idx is not None and self.total_items is not None:
            return f"[{idx}/{self.total_items}]"
        if idx is not None:
            return f"[{idx}]"
        return ""

    @staticmethod
    def _timestamp() -> str:
        """Return current wall-clock time as ``HH:MM:SS``."""
        return datetime.now(tz=timezone.utc).strftime("%H:%M:%S")

    def _write(self, event: UIEvent, message: str) -> None:
        """Write a formatted line to the stream."""
        ts = self._timestamp()
        tag = self._progress_tag(event)
        if tag:
            line = f"[{ts}] {tag} {event.identifier}: {message}"
        else:
            line = f"[{ts}] {event.identifier}: {message}"
        self.stream.write(line + "\n")
        self.stream.flush()
