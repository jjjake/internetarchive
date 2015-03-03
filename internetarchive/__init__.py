# -*- coding: utf-8 -*-
"""
Internetarchive Library
~~~~~~~~~~~~~~~~~~~~~~~

Internetarchive is a python interface to archive.org.
usage:

    >>> from internetarchive import get_item
    >>> item = get_item('govlawgacode20071')
    >>> item.exists
    True

:copyright: (c) 2015 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.

"""

__title__ = 'internetarchive'
__author__ = 'Jacob M. Johnson'
__license__ = 'AGPL 3'
__copyright__ = 'Copyright 2013 Internet Archive'

from .item import Item, File
from .search import Search
from .catalog import Catalog
from .api import get_item, get_files, iter_files, modify_metadata, upload, download, \
    delete, get_tasks, search_items

from ._version import __version__


__all__ = [
    '__version__',

    # Classes.
    'Item',
    'File',
    'Search',
    'Catalog',

    # API.
    'get_item',
    'get_files',
    'iter_files',
    'modify_metadata',
    'upload',
    'download',
    'delete',
    'get_tasks',
    'search_items',
]


# Set default logging handler to avoid "No handler found" warnings.
import logging
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass


log = logging.getLogger('internetarchive')
log.addHandler(NullHandler())


from pkg_resources import iter_entry_points, load_entry_point
for object in iter_entry_points(group='internetarchive.plugins', name=None):
    try:
        globals()[object.name] = load_entry_point(
            object.dist, 'internetarchive.plugins', object.name)
        __all__.append(object.name)
    except ImportError:
        log.warning('Failed to import plugin: {}'.format(object.name))
