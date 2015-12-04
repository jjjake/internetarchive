# -*- coding: utf-8 -*-
"""
Internetarchive Library
~~~~~~~~~~~~~~~~~~~~~~~

Internetarchive is a python interface to archive.org.

Usage::

    >>> from internetarchive import get_item
    >>> item = get_item('govlawgacode20071')
    >>> item.exists
    True

:copyright: (c) 2015 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

__title__ = 'internetarchive'
__version__ = '1.0.0.dev2'
__author__ = 'Jacob M. Johnson'
__license__ = 'AGPL 3'
__copyright__ = 'Copyright 2015 Internet Archive'

from internetarchive.item import Item
from internetarchive.files import File
from internetarchive.search import Search
from internetarchive.catalog import Catalog
from internetarchive.session import ArchiveSession
from internetarchive.api import get_item, get_files, modify_metadata, upload, \
                                download, delete, get_tasks, search_items, \
                                get_session, configure


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


from pkg_resources import iter_entry_points, load_entry_point
for object in iter_entry_points(group='internetarchive.plugins', name=None):
    try:
        globals()[object.name] = load_entry_point(
            object.dist, 'internetarchive.plugins', object.name)
        __all__.append(object.name)
    except ImportError:
        log.warning('Failed to import plugin: {}'.format(object.name))
