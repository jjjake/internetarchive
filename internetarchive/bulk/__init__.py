# Bulk operations engine for internetarchive.
#
# Copyright (C) 2012-2026 Internet Archive
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
internetarchive.bulk
~~~~~~~~~~~~~~~~~~~~

Bulk operations engine for concurrent item processing.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

__all__ = [
    "BaseWorker",
    "BulkEngine",
    "JobLog",
    "WorkerResult",
]


def __getattr__(name):
    if name == "BulkEngine":
        from internetarchive.bulk.engine import BulkEngine  # noqa: PLC0415
        return BulkEngine
    if name == "JobLog":
        from internetarchive.bulk.joblog import JobLog  # noqa: PLC0415
        return JobLog
    if name in ("BaseWorker", "WorkerResult"):
        from internetarchive.bulk import worker  # noqa: PLC0415
        return getattr(worker, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
