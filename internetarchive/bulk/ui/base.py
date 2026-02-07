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
internetarchive.bulk.ui.base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Base UI types for bulk operations.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UIEvent:
    """An event emitted by the bulk engine for UI consumption.

    Attributes:
        kind: The type of event (e.g., "item_started", "item_completed",
            "item_failed", "item_skipped", "file_progress", "disk_update").
        identifier: The Archive.org item identifier this event relates to.
        worker: The worker index that produced this event.
        item_index: The 1-based position of this item in the overall queue.
        filename: The file this event relates to, if applicable.
        bytes_done: Bytes completed so far for this file or item.
        bytes_total: Total expected bytes for this file or item.
        elapsed: Elapsed time in seconds for the operation.
        files_ok: Number of files successfully processed so far.
        error: Error message, if this event represents a failure.
    """

    kind: str
    identifier: str
    worker: int
    item_index: int | None = None
    filename: str | None = None
    bytes_done: int | None = None
    bytes_total: int | None = None
    elapsed: float | None = None
    files_ok: int | None = None
    error: str | None = None
