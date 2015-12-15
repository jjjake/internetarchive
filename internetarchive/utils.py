# -*- coding: utf-8 -*-
"""
internetarchive.utils
~~~~~~~~~~~~~~~~~~~~~

This module provides utility functions for the internetarchive library.

:copyright: (c) 2015 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
import sys
import hashlib
import os
import re
from itertools import starmap
from six.moves import zip_longest
from collections import Mapping


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
    legal_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
    assert 80 >= len(string) >= 3
    assert all(c in legal_chars for c in string)
    return True


def needs_quote(s):
    try:
        s.encode('ascii')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return True
    return re.search(r'\s', s) is not None


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
