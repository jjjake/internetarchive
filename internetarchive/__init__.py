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
Internetarchive Library
~~~~~~~~~~~~~~~~~~~~~~~

Internetarchive is a python interface to archive.org.

Usage::

    >>> from internetarchive import get_item
    >>> item = get_item('govlawgacode20071')
    >>> item.exists
    True

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import absolute_import

__title__ = 'internetarchive'
__version__ = '1.0.3'
__author__ = 'Jacob M. Johnson'
__license__ = 'AGPL 3'
__copyright__ = 'Copyright (C) 2012-2016 Internet Archive'

from internetarchive.item import Item
from internetarchive.files import File
from internetarchive.search import Search
from internetarchive.catalog import Catalog
from internetarchive.session import ArchiveSession
from internetarchive.api import get_item, get_files, modify_metadata, upload, \
    download, delete, get_tasks, search_items, get_session, configure, get_username


__all__ = [
    '__version__',

    # Classes.
    'ArchiveSession',
    'Item',
    'File',
    'Search',
    'Catalog',

    # API.
    'get_item',
    'get_files',
    'modify_metadata',
    'upload',
    'download',
    'delete',
    'get_tasks',
    'search_items',
    'get_session',
    'configure',
    'get_username',
]


# Set default logging handler to avoid "No handler found" warnings.
import logging
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass


log = logging.getLogger(__name__)
log.addHandler(NullHandler())
