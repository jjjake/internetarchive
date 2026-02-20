"""
internetarchive.bulk.joblog
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

JSONL-based job log for tracking bulk operations.

A single JSONL file per session serves as both job manifest and event
log. Append-only writes with per-write locking and flushing.

Resume is powered by a compact bitmap: sequence numbers map to bits,
so 10M items require only ~1.2 MB of memory.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import IO, Iterator

_MAX_SEQ = 100_000_000  # 100M items → ~12.5 MB bitmap


class Bitmap:
    """Compact bit array for tracking completed job sequences.

    :param size: Number of bits to allocate. Automatically grows
        if ``set()`` is called with a value beyond current capacity.
    """

    def __init__(self, size: int = 0):
        self._data = bytearray((size + 7) // 8) if size else bytearray()

    def set(self, n: int) -> None:
        """Mark bit *n* as set, growing the array if needed.

        :raises ValueError: If *n* is negative or exceeds
            ``_MAX_SEQ``.
        """
        if n < 0:
            raise ValueError(
                f"Bitmap index must be non-negative, got {n}"
            )
        if n > _MAX_SEQ:
            raise ValueError(
                f"Bitmap index {n} exceeds maximum {_MAX_SEQ}"
            )
        byte_idx = n >> 3
        if byte_idx >= len(self._data):
            self._data.extend(
                b"\x00" * (byte_idx - len(self._data) + 1)
            )
        self._data[byte_idx] |= 1 << (n & 7)

    @property
    def size_bytes(self) -> int:
        """Return the size of the underlying byte array."""
        return len(self._data)

    def __contains__(self, n: int) -> bool:
        if n < 0:
            return False
        byte_idx = n >> 3
        if byte_idx >= len(self._data):
            return False
        return bool(self._data[byte_idx] & (1 << (n & 7)))


def _ts() -> str:
    """Return a compact UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class JobLog:
    """Append-only JSONL job log with resume support.

    :param path: Path to the JSONL log file. Created if it does
        not exist.

    Usage::

        log = JobLog("my_session.jsonl")

        # Resolve phase: write job lines
        log.write_job(seq=1, identifier="foo", op="download")
        log.write_job(seq=2, identifier="bar", op="download")

        # Execute phase: write event lines
        log.write_event("started", seq=1, worker=0)
        log.write_event("completed", seq=1, extra={"bytes": 1024})
        log.write_event("failed", seq=2, error="HTTP 503", retry=1)

        # Resume: get bitmap of completed sequences
        bitmap = log.build_resume_bitmap()
        for job in log.iter_pending_jobs(bitmap):
            ...  # re-process
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._fh: IO[str] | None = None

    def _ensure_open(self) -> IO[str]:
        """Open the file handle for appending, creating if needed."""
        if self._fh is None or self._fh.closed:
            self._fh = open(self.path, "a", encoding="utf-8")
        return self._fh

    def close(self) -> None:
        """Close the file handle."""
        if self._fh and not self._fh.closed:
            self._fh.close()
            self._fh = None

    def _append(self, record: dict, sync: bool = False) -> None:
        """Write a single JSON line, thread-safe with flush.

        :param record: Dict to serialize as JSON.
        :param sync: If ``True``, call ``fsync`` after writing.
            Used for event lines (started/completed/failed) where
            crash recovery correctness matters. Job lines skip
            fsync for performance during the resolve phase.
        """
        line = json.dumps(record, separators=(",", ":"))
        with self._lock:
            fh = self._ensure_open()
            fh.write(line + "\n")
            fh.flush()
            if sync:
                os.fsync(fh.fileno())

    def write_job(
        self,
        seq: int,
        identifier: str,
        op: str,
        **extra: object,
    ) -> None:
        """Write a job line during the resolve phase.

        :param seq: Sequence number (1-based).
        :param identifier: Archive.org item identifier.
        :param op: Operation name (e.g. ``"download"``).
        :param extra: Additional key-value pairs to include.
        """
        record: dict = {
            "event": "job",
            "seq": seq,
            "id": identifier,
            "op": op,
            "ts": _ts(),
        }
        if extra:
            record.update(extra)
        self._append(record)

    def write_event(
        self,
        event: str,
        seq: int,
        **kwargs: object,
    ) -> None:
        """Write an event line during the execute phase.

        :param event: Event type (``"started"``, ``"completed"``,
            ``"failed"``).
        :param seq: Job sequence number this event refers to.
        :param kwargs: Additional fields (``worker``, ``error``,
            ``retry``, ``extra``).
        """
        record: dict = {"event": event, "seq": seq, "ts": _ts()}
        record.update(kwargs)
        self._append(record, sync=True)

    def build_resume_bitmap(self) -> Bitmap:
        """Scan the log and build a bitmap of completed sequences.

        Completed and permanently-skipped sequences are marked.
        Malformed trailing lines (crash recovery) are silently
        skipped.

        :returns: A ``Bitmap`` with completed sequences set.
        """
        bitmap = Bitmap()
        for record in self._iter_records():
            seq = record.get("seq", -1)
            if seq < 0 or seq > _MAX_SEQ:
                continue
            if record.get("event") == "completed":
                bitmap.set(seq)
            elif (
                record.get("event") == "failed"
                and record.get("retry") is False
            ):
                bitmap.set(seq)
        return bitmap

    def iter_pending_jobs(
        self, bitmap: Bitmap
    ) -> Iterator[dict]:
        """Yield job records not in the bitmap.

        :param bitmap: Bitmap of completed/skipped sequences.
        :returns: Iterator of job dicts that still need processing.
        """
        for record in self._iter_records():
            if record.get("event") != "job":
                continue
            if record["seq"] not in bitmap:
                yield record

    def get_max_seq(self) -> int:
        """Return the highest sequence number in the log.

        :returns: Max sequence number, or 0 if empty.
        """
        max_seq = 0
        for record in self._iter_records():
            if record.get("event") == "job":
                seq = record.get("seq", 0)
                max_seq = max(max_seq, seq)
        return max_seq

    def status(self) -> dict:
        """Return a summary of the joblog.

        :returns: Dict with keys ``total``, ``completed``,
            ``failed``, ``pending``.
        """
        total = 0
        completed = set()
        permanently_failed = set()
        for record in self._iter_records():
            event = record.get("event")
            if event == "job":
                total += 1
            elif event == "completed":
                completed.add(record["seq"])
            elif event == "failed" and record.get("retry") is False:
                permanently_failed.add(record["seq"])
        done = completed | permanently_failed
        return {
            "total": total,
            "completed": len(completed),
            "failed": len(permanently_failed),
            "pending": total - len(done),
        }

    def load(self) -> dict:
        """Single-pass scan that computes all resume state at once.

        :returns: Dict with keys ``max_seq``, ``bitmap``,
            ``pending``, ``status``.

        Much faster than calling ``get_max_seq()``,
        ``build_resume_bitmap()``, ``iter_pending_jobs()``, and
        ``status()`` separately (which each re-read the file).
        """
        max_seq = 0
        total = 0
        bitmap = Bitmap()
        jobs: list[dict] = []
        completed = set()
        permanently_failed = set()

        for record in self._iter_records():
            event = record.get("event")
            seq = record.get("seq", -1)
            if seq < 0 or seq > _MAX_SEQ:
                continue
            if event == "job":
                total += 1
                max_seq = max(max_seq, seq)
                jobs.append(record)
            elif event == "completed":
                bitmap.set(seq)
                completed.add(seq)
            elif event == "failed" and record.get("retry") is False:
                bitmap.set(seq)
                permanently_failed.add(seq)

        pending = [j for j in jobs if j["seq"] not in bitmap]
        done = completed | permanently_failed

        return {
            "max_seq": max_seq,
            "bitmap": bitmap,
            "pending": pending,
            "status": {
                "total": total,
                "completed": len(completed),
                "failed": len(permanently_failed),
                "pending": total - len(done),
            },
        }

    def _iter_records(self) -> Iterator[dict]:
        """Iterate over all valid JSON records in the log file.

        Malformed lines are silently skipped (crash recovery).
        """
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
