# -*- coding: utf-8 -*-
"""
internetarchive.cli
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2015 Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from pkg_resources import iter_entry_points, load_entry_point

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


# Load internetarchive.cli plugins, and add to __all__.
for object in iter_entry_points(group='internetarchive.cli.plugins', name=None):
    __all__.append(object.name)
    globals()[object.name] = load_entry_point(
        object.dist, 'internetarchive.cli.plugins', object.name)
