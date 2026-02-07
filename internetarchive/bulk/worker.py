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
internetarchive.bulk.worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Worker interface and result types for bulk operations.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WorkerResult:
    """Result of a single bulk operation on one identifier.

    Attributes:
        success: Whether the operation completed without errors.
        identifier: The Archive.org item identifier.
        bytes_transferred: Total bytes transferred during the operation.
        files_ok: Number of files successfully processed.
        files_skipped: Number of files skipped (e.g., already present).
        files_failed: Number of files that failed to process.
        error: Error message if the operation failed, otherwise None.
    """

    success: bool
    identifier: str
    bytes_transferred: int = 0
    files_ok: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    error: str | None = None


@dataclass
class VerifyResult:
    """Result of verifying a completed operation for one identifier.

    Attributes:
        identifier: The Archive.org item identifier.
        complete: Whether all expected files are present and intact.
        files_expected: Total number of files expected.
        files_found: Number of files actually found on disk.
        files_missing: List of filenames that are missing.
        files_corrupted: List of filenames that failed checksum verification.
    """

    identifier: str
    complete: bool
    files_expected: int
    files_found: int
    files_missing: list[str] = field(default_factory=list)
    files_corrupted: list[str] = field(default_factory=list)


class BaseWorker(ABC):
    """Abstract base class for bulk operation workers.

    The BulkEngine calls these methods without knowing what operation
    is being performed. Concrete implementations handle specific
    operations like download, upload, etc.
    """

    @abstractmethod
    def estimate_size(self, identifier: str) -> int | None:
        """Estimate the total size in bytes for an operation on an identifier.

        Args:
            identifier: The Archive.org item identifier.

        Returns:
            Estimated size in bytes, or None if the size cannot be
            determined.
        """

    @abstractmethod
    def execute(self, identifier: str, destdir: Path) -> WorkerResult:
        """Execute the operation for a single identifier.

        Args:
            identifier: The Archive.org item identifier.
            destdir: The destination directory for the operation.

        Returns:
            A WorkerResult describing the outcome.
        """

    @abstractmethod
    def verify(self, identifier: str, destdir: Path) -> VerifyResult:
        """Verify the result of a completed operation.

        Args:
            identifier: The Archive.org item identifier.
            destdir: The destination directory to verify against.

        Returns:
            A VerifyResult describing the verification outcome.
        """
