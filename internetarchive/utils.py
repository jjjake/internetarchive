# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2017 Internet Archive
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
internetarchive.utils
~~~~~~~~~~~~~~~~~~~~~

This module provides utility functions for the internetarchive library.

:copyright: (C) 2012-2017 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
import hashlib
import os
import re
import sys
from collections import Mapping
from itertools import starmap
from xml.dom.minidom import parseString

import six
from six.moves import zip_longest


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = deep_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def map2x(func, *iterables):
    """map() function for Python 2/3 compatability"""
    zipped = zip_longest(*iterables)
    if func is None:
        return zipped
    return starmap(func, zipped)


def validate_ia_identifier(string):
    legal_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-'
    # periods, underscores, and dashes are legal, but may not be the first
    # character!
    assert all(string.startswith(c) is False for c in ['.', '_', '-'])
    assert 100 >= len(string) >= 3
    assert all(c in legal_chars for c in string)
    return True


def needs_quote(s):
    try:
        s.encode('ascii')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return True
    return re.search(r'\s', s) is not None


def norm_filepath(fp):
    fp = fp.replace(os.path.sep, '/')
    if not fp[0] == '/':
        fp = '/' + fp
    if isinstance(fp, six.binary_type):
        fp = fp.decode('utf-8')
    return fp


def get_md5(file_object):
    m = hashlib.md5()
    while True:
        data = file_object.read(8192)
        if not data:
            break
        m.update(data)
    file_object.seek(0, os.SEEK_SET)
    return m.hexdigest()


def chunk_generator(fp, chunk_size):
    while True:
        chunk = fp.read(chunk_size)
        if not chunk:
            break
        yield chunk


def suppress_keyboard_interrupt_message():
    """Register a new excepthook to suppress KeyboardInterrupt
    exception messages, and exit with status code 130.

    """
    old_excepthook = sys.excepthook

    def new_hook(type, value, traceback):
        if type != KeyboardInterrupt:
            old_excepthook(type, value, traceback)
        else:
            sys.exit(130)

    sys.excepthook = new_hook


class IterableToFileAdapter(object):
    def __init__(self, iterable, size):
        self.iterator = iter(iterable)
        self.length = size

    def read(self, size=-1):  # TBD: add buffer for `len(data) > size` case
        return next(self.iterator, b'')

    def __len__(self):
        return self.length


class IdentifierListAsItems(object):
    """This class is a lazily-loaded list of Items, accessible by index or identifier.
    """

    def __init__(self, id_list_or_single_id, session):
        self.ids = id_list_or_single_id \
            if isinstance(id_list_or_single_id, list) \
            else [id_list_or_single_id]

        self._items = [None] * len(self.ids)
        self.session = session

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, idx):
        for i in (range(*idx.indices(len(self))) if isinstance(idx, slice) else [idx]):
            if self._items[i] is None:
                self._items[i] = self.session.get_item(self.ids[i])
        return self._items[idx]

    def __getattr__(self, name):
        try:
            return self[self.ids.index(name)]
        except ValueError:
            raise AttributeError

    def __repr__(self):
        return '{0.__class__.__name__}({0.ids!r})'.format(self)


def get_s3_xml_text(xml_str):
    def _get_tag_text(tag_name, xml_obj):
        text = ''
        elements = xml_obj.getElementsByTagName(tag_name)
        for e in elements:
            for node in e.childNodes:
                if node.nodeType == node.TEXT_NODE:
                    text += node.data
        return text

    tag_names = ['Message', 'Resource']
    try:
        p = parseString(xml_str)
        _msg = _get_tag_text('Message', p)
        _resource = _get_tag_text('Resource', p)
        # Avoid weird Resource text that contains PUT method.
        if _resource and "'PUT" not in _resource:
            return '{0} - {1}'.format(_msg, _resource.strip())
        else:
            return _msg
    except:
        return str(xml_str)


def get_file_size(file_obj):
    try:
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        # Avoid OverflowError.
        if size > sys.maxsize:
            size = None
        file_obj.seek(0, os.SEEK_SET)
    except IOError:
        size = None
    return size


def iter_directory(directory):
    """Given a directory, yield all files recursivley as a two-tuple (filepath, s3key)"""
    for path, dir, files in os.walk(directory):
        for f in files:
            filepath = os.path.join(path, f)
            key = os.path.relpath(filepath, directory)
            yield (filepath, key)


def recursive_file_count(files, item=None, checksum=False):
    """Given a filepath or list of filepaths, return the total number of files."""
    if not isinstance(files, (list, set)):
        files = [files]
    total_files = 0
    if checksum is True:
        md5s = [f.get('md5') for f in item.files]
    else:
        md5s = list()
    if isinstance(files, dict):
        # make sure to use local filenames.
        _files = files.values()
        print(_files)
    else:
        if isinstance(files[0], tuple):
            _files = dict(files).values()
        else:
            _files = files
    for f in _files:
        try:
            is_dir = os.path.isdir(f)
        except TypeError:
            try:
                f = f[0]
                is_dir = os.path.isdir(f)
            except AttributeError:
                is_dir = False
        if is_dir:
            for x, _ in iter_directory(f):
                lmd5 = get_md5(open(x, 'rb'))
                if lmd5 in md5s:
                    continue
                else:
                    total_files += 1
        else:
            try:
                lmd5 = get_md5(open(f, 'rb'))
            except TypeError:
                # Support file-like objects.
                lmd5 = get_md5(f)
            if lmd5 in md5s:
                continue
            else:
                total_files += 1
    return total_files
