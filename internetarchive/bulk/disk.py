"""
internetarchive.bulk.disk
~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-disk routing for bulk downloads.

``DiskPool`` manages space reservations across one or more
destination directories, ensuring partial items never land on a
disk without enough room.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import shutil
import threading

# Default space margin: 1 GB
DEFAULT_MARGIN = 1024 * 1024 * 1024


class DiskPool:
    """Multi-disk router for downloads.

    Picks the disk with the most available space that can fit the
    estimated download size plus margin. Thread-safe.

    :param paths: List of destination directory paths.
    :param margin: Minimum free space to maintain on each disk
        (bytes). Defaults to 1 GB.
    :param check_space: If ``False``, disables disk space checking.
        Always routes to the first path.
    """

    def __init__(
        self,
        paths: list[str],
        margin: int = DEFAULT_MARGIN,
        check_space: bool = True,
    ):
        if not paths:
            raise ValueError("DiskPool requires at least one path")
        self.paths = list(paths)
        self.margin = margin
        self.check_space = check_space
        self._lock = threading.Lock()
        # Track bytes reserved but not yet released per path
        self._reserved: dict[str, int] = dict.fromkeys(self.paths, 0)

    def route(self, estimated_bytes: int = 0) -> str | None:
        """Choose a disk with enough space for the download.

        :param estimated_bytes: Estimated download size in bytes.
        :returns: Path to use, or ``None`` if no disk has enough
            space (caller should trigger backoff).
        """
        if not self.check_space:
            return self.paths[0]

        with self._lock:
            best_path = None
            best_free = -1

            for path in self.paths:
                try:
                    usage = shutil.disk_usage(path)
                except OSError:
                    continue
                reserved = self._reserved.get(path, 0)
                available = usage.free - reserved - self.margin
                if available >= estimated_bytes and available > best_free:
                    best_free = available
                    best_path = path

            if best_path is not None:
                self._reserved[best_path] = (
                    self._reserved.get(best_path, 0) + estimated_bytes
                )

            return best_path

    def release(self, path: str, estimated_bytes: int = 0) -> None:
        """Release a space reservation after download completes.

        :param path: The path that was returned by ``route()``.
        :param estimated_bytes: The same estimate passed to
            ``route()``.
        """
        with self._lock:
            current = self._reserved.get(path, 0)
            self._reserved[path] = max(0, current - estimated_bytes)
