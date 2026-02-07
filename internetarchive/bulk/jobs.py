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
internetarchive.bulk.jobs
~~~~~~~~~~~~~~~~~~~~~~~~~~

JSONL-based job tracking with resume semantics for bulk operations.

Each line in the JSONL file represents one item-level event with fields:
  ts   - ISO 8601 UTC timestamp
  op   - operation name (e.g. "download")
  id   - Archive.org item identifier
  event - one of: started, completed, failed, skipped, rerouted

Plus event-specific fields depending on the event type.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self

# Skip reasons that indicate the item should not be retried.
_PERMANENT_SKIP_REASONS = frozenset({"exists", "dark", "empty"})


class JobLog:
    """Append-only JSONL job log with resume semantics.

    Thread-safe: all writes are serialized through a threading.Lock.

    Args:
        path: Path to the JSONL log file. Will be created if it does
            not exist. If it already exists, existing events are loaded
            to restore in-memory state for resume decisions.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        # In-memory state for resume decisions.
        # Maps identifier -> final "effective" state tuple:
        #   ("completed", None)
        #   ("skipped", reason)
        #   ("failed", error)
        #   ("started", None)
        self._items: dict[str, tuple[str, str | None]] = {}
        # Aggregated stats for completed items.
        self._completed_bytes: dict[str, int] = {}
        self._completed_files_ok: dict[str, int] = {}

        # Load existing file if present.
        if self._path.exists():
            self._replay_existing()

        # Open file for appending.
        self._fh = open(self._path, "a")

    def _replay_existing(self) -> None:
        """Replay an existing JSONL file to restore in-memory state."""
        with open(self._path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                self._apply_record(rec)

    def _apply_record(self, rec: dict) -> None:
        """Update in-memory state from a single parsed record."""
        identifier = rec["id"]
        event = rec["event"]

        if event == "completed":
            self._items[identifier] = ("completed", None)
            self._completed_bytes[identifier] = rec.get(
                "bytes_transferred", 0
            )
            self._completed_files_ok[identifier] = rec.get("files_ok", 0)
        elif event == "skipped":
            # Only store skip if not already completed (completed is sticky).
            if self._items.get(identifier, (None,))[0] != "completed":
                self._items[identifier] = ("skipped", rec.get("reason"))
        elif event == "failed":
            if self._items.get(identifier, (None,))[0] != "completed":
                self._items[identifier] = ("failed", rec.get("error"))
        elif event == "started":
            if self._items.get(identifier, (None,))[0] != "completed":
                self._items[identifier] = ("started", None)
        # rerouted events do not change resume state

    def _write(self, rec: dict) -> None:
        """Write a record to the JSONL file and update in-memory state."""
        rec["ts"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(rec, separators=(",", ":"))
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()
            self._apply_record(rec)

    # -- Public logging methods ----------------------------------------

    def log_started(
        self,
        identifier: str,
        *,
        op: str,
        destdir: str,
        est_bytes: int,
        worker: str,
        retry: int,
    ) -> None:
        """Log that work has started on an identifier."""
        self._write({
            "id": identifier,
            "event": "started",
            "op": op,
            "destdir": destdir,
            "est_bytes": est_bytes,
            "worker": worker,
            "retry": retry,
        })

    def log_completed(
        self,
        identifier: str,
        *,
        op: str,
        destdir: str,
        bytes_transferred: int,
        files_ok: int,
        files_skipped: int,
        files_failed: int,
        elapsed: float,
    ) -> None:
        """Log that an identifier completed successfully."""
        self._write({
            "id": identifier,
            "event": "completed",
            "op": op,
            "destdir": destdir,
            "bytes_transferred": bytes_transferred,
            "files_ok": files_ok,
            "files_skipped": files_skipped,
            "files_failed": files_failed,
            "elapsed": elapsed,
        })

    def log_failed(
        self,
        identifier: str,
        *,
        op: str,
        error: str,
        retries_left: int,
    ) -> None:
        """Log that an identifier failed."""
        self._write({
            "id": identifier,
            "event": "failed",
            "op": op,
            "error": error,
            "retries_left": retries_left,
        })

    def log_skipped(
        self,
        identifier: str,
        *,
        op: str,
        reason: str,
    ) -> None:
        """Log that an identifier was skipped.

        Args:
            identifier: The Archive.org item identifier.
            op: The operation name.
            reason: One of "exists", "no_disk_space", "dark", "empty".
        """
        self._write({
            "id": identifier,
            "event": "skipped",
            "op": op,
            "reason": reason,
        })

    def log_rerouted(
        self,
        identifier: str,
        *,
        op: str,
        from_destdir: str,
        to_destdir: str,
        reason: str,
    ) -> None:
        """Log that an identifier was rerouted to a different destination."""
        self._write({
            "id": identifier,
            "event": "rerouted",
            "op": op,
            "from_destdir": from_destdir,
            "to_destdir": to_destdir,
            "reason": reason,
        })

    # -- Resume semantics ----------------------------------------------

    def should_skip(self, identifier: str) -> bool:
        """Determine whether an identifier should be skipped on resume.

        Rules:
          - completed -> True (always skip)
          - skipped with reason "exists"/"dark"/"empty" -> True
          - skipped with reason "no_disk_space" -> False (retry)
          - failed -> False (retry)
          - started with no completion -> False (crash recovery)
          - unknown identifier -> False
        """
        with self._lock:
            state = self._items.get(identifier)

        if state is None:
            return False

        event, detail = state
        if event == "completed":
            return True
        if event == "skipped":
            return detail in _PERMANENT_SKIP_REASONS
        # failed, started, or anything else -> retry
        return False

    # -- Status summary ------------------------------------------------

    def status(self) -> dict:
        """Compute summary statistics from the current in-memory state.

        Returns a dict with keys:
          completed     - number of completed items
          failed        - number of items whose last event was "failed"
          skipped       - number of items whose last event was "skipped"
          total_bytes   - sum of bytes_transferred across completed items
          total_files_ok - sum of files_ok across completed items
          failed_items  - list of (identifier, error) tuples for failed items
        """
        with self._lock:
            items_snapshot = dict(self._items)
            bytes_snapshot = dict(self._completed_bytes)
            files_ok_snapshot = dict(self._completed_files_ok)

        completed = 0
        failed = 0
        skipped = 0
        failed_items: list[tuple[str, str]] = []

        for identifier, (event, detail) in items_snapshot.items():
            if event == "completed":
                completed += 1
            elif event == "failed":
                failed += 1
                failed_items.append((identifier, detail or ""))
            elif event == "skipped":
                skipped += 1

        total_bytes = sum(bytes_snapshot.values())
        total_files_ok = sum(files_ok_snapshot.values())

        return {
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "total_bytes": total_bytes,
            "total_files_ok": total_files_ok,
            "failed_items": failed_items,
        }

    # -- Lifecycle -----------------------------------------------------

    def close(self) -> None:
        """Flush and close the file handle."""
        with self._lock:
            if self._fh and not self._fh.closed:
                self._fh.flush()
                self._fh.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
