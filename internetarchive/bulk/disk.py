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
internetarchive.bulk.disk
~~~~~~~~~~~~~~~~~~~~~~~~~~

Disk space monitoring and routing for bulk operations.

Provides :func:`parse_size` for parsing human-readable size strings
and :class:`DiskPool` for routing work to destination directories
with sufficient free space.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import os
import re
import threading
from collections import defaultdict

_SUFFIXES: dict[str, int] = {
    "K": 1024,
    "M": 1024**2,
    "G": 1024**3,
    "T": 1024**4,
}

_SIZE_RE = re.compile(r"^\s*(\d+)\s*([KMGT])?\s*$", re.IGNORECASE)


def parse_size(s: str) -> int:
    """Parse a human-readable size string to bytes.

    Accepted formats: ``"1024"``, ``"100K"``, ``"500M"``, ``"1G"``,
    ``"2T"``.  A trailing ``B`` is tolerated (e.g. ``"1GB"``).
    Parsing is case-insensitive.

    Args:
        s: The size string to parse.

    Returns:
        The size in bytes.

    Raises:
        ValueError: If *s* cannot be parsed as a valid size.
    """
    # Strip optional trailing 'B' (as in "1GB", "500MB").
    normalized = s.strip()
    if normalized.upper().endswith("B") and not normalized.isdigit():
        normalized = normalized[:-1]

    m = _SIZE_RE.match(normalized)
    if not m:
        raise ValueError(f"Invalid size string: {s!r}")

    number = int(m.group(1))
    suffix = m.group(2)
    if suffix:
        return number * _SUFFIXES[suffix.upper()]
    return number


class DiskPool:
    """Monitors disk space across destination directories and routes work.

    Each call to :meth:`route` finds the first directory with enough
    free space, *reserves* the estimated bytes so concurrent workers
    don't overcommit, and returns the directory path.  After a worker
    finishes, :meth:`release` frees the reservation.

    Args:
        destdirs: Ordered list of destination directory paths.
        margin: Bytes to keep free on every disk (default 1 GiB).
        disabled: When ``True``, bypass space checks and always
            return the first directory.
    """

    def __init__(
        self,
        destdirs: list[str],
        margin: int = 1024**3,
        disabled: bool = False,
    ) -> None:
        self._destdirs: list[str] = list(destdirs)
        self._margin = margin
        self._disabled = disabled

        self._lock = threading.Lock()
        # Total reserved bytes per directory.
        self._reserved: dict[str, int] = defaultdict(int)
        # Number of in-flight items per directory.
        self._in_flight: dict[str, int] = defaultdict(int)
        # Directories marked full (removed from routing).
        self._full: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, est_bytes: int | None) -> str | None:
        """Find a destination directory with enough space and reserve it.

        Args:
            est_bytes: Estimated bytes needed.  If ``None``, uses
                ``2 * margin`` as a conservative estimate.

        Returns:
            The chosen directory path, or ``None`` if no directory
            has enough free space.
        """
        if self._disabled:
            return self._destdirs[0] if self._destdirs else None

        size = est_bytes if est_bytes is not None else 2 * self._margin

        with self._lock:
            for d in self._destdirs:
                if d in self._full:
                    continue
                if self._available_unlocked(d) >= size:
                    self._reserved[d] += size
                    self._in_flight[d] += 1
                    return d
        return None

    def available(self, destdir: str) -> int:
        """Return usable free bytes on *destdir*.

        This is the filesystem free space minus the safety margin
        and any outstanding reservations.
        """
        with self._lock:
            return self._available_unlocked(destdir)

    def release(self, destdir: str, est_bytes: int) -> None:
        """Release a reservation after a worker completes.

        Args:
            destdir: The directory previously returned by :meth:`route`.
            est_bytes: The same estimate passed to :meth:`route`.
        """
        with self._lock:
            self._reserved[destdir] = max(
                0, self._reserved[destdir] - est_bytes
            )
            self._in_flight[destdir] = max(
                0, self._in_flight[destdir] - 1
            )

    def mark_full(self, destdir: str) -> None:
        """Remove *destdir* from future routing (e.g. after ``ENOSPC``)."""
        with self._lock:
            self._full.add(destdir)

    def in_flight_count(self, destdir: str) -> int:
        """Return the number of items currently in-flight to *destdir*."""
        with self._lock:
            return self._in_flight.get(destdir, 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _available_unlocked(self, destdir: str) -> int:
        """Compute available bytes without acquiring the lock."""
        st = os.statvfs(destdir)
        free = st.f_bavail * st.f_frsize
        return max(0, free - self._margin - self._reserved[destdir])
