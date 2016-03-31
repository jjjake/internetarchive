# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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
internetarchive.cli
~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from internetarchive.cli import ia, ia_configure, ia_delete, ia_download, ia_list, \
    ia_metadata, ia_search, ia_tasks, ia_upload, argparser


__all__ = [
    'ia',
    'ia_configure',
    'ia_delete',
    'ia_download',
    'ia_list',
    'ia_metadata',
    'ia_search',
    'ia_tasks',
    'ia_upload',
    'argparser',
]
