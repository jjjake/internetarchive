# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2018 Internet Archive
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

:copyright: (C) 2012-2018 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
import hashlib
import os
import re
import sys
from collections import Mapping
from itertools import starmap
from xml.dom.minidom import parseString
import copy
try:
    import ujson as json
except ImportError:
    import json

import six
from six.moves import zip_longest, urllib
from jsonpatch import make_patch

from internetarchive import __version__


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
            except (AttributeError, TypeError):
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


def is_dir(obj):
    """Special is_dir function to handle file-like object cases that
    cannot be stat'd"""
    try:
        return os.path.isdir(obj)
    except TypeError as exc:
        return False


def prepare_metadata(metadata, source_metadata=None, append=False, append_list=False):
    """Prepare a metadata dict for an
    :class:`S3PreparedRequest <S3PreparedRequest>` or
    :class:`MetadataPreparedRequest <MetadataPreparedRequest>` object.

    :type metadata: dict
    :param metadata: The metadata dict to be prepared.

    :type source_metadata: dict
    :param source_metadata: (optional) The source metadata for the item
                            being modified.

    :rtype: dict
    :returns: A filtered metadata dict to be used for generating IA
              S3 and Metadata API requests.

    """
    # Make a deepcopy of source_metadata if it exists. A deepcopy is
    # necessary to avoid modifying the original dict.
    source_metadata = {} if not source_metadata else copy.deepcopy(source_metadata)
    prepared_metadata = {}

    # Functions for dealing with metadata keys containing indexes.
    def get_index(key):
        match = re.search(r'(?<=\[)\d+(?=\])', key)
        if match is not None:
            return int(match.group())

    def rm_index(key):
        return key.split('[')[0]

    # Create indexed_keys counter dict. i.e.: {'subject': 3} -- subject
    # (with the index removed) appears 3 times in the metadata dict.
    indexed_keys = {}
    for key in metadata:
        # Convert number values to strings!
        if isinstance(metadata[key], (six.integer_types, float, complex)):
            metadata[key] = str(metadata[key])
        if get_index(key) is None:
            continue
        count = len([x for x in metadata if rm_index(x) == rm_index(key)])
        indexed_keys[rm_index(key)] = count

    # Initialize the values for all indexed_keys.
    for key in indexed_keys:
        # Increment the counter so we know how many values the final
        # value in prepared_metadata should have.
        indexed_keys[key] += len(source_metadata.get(key, []))
        # Intialize the value in the prepared_metadata dict.
        prepared_metadata[key] = source_metadata.get(key, [])
        if not isinstance(prepared_metadata[key], list):
            prepared_metadata[key] = [prepared_metadata[key]]
        # Fill the value of the prepared_metadata key with None values
        # so all indexed items can be indexed in order.
        while len(prepared_metadata[key]) < indexed_keys[key]:
            prepared_metadata[key].append(None)

    # Index all items which contain an index.
    for key in metadata:
        # Insert values from indexed keys into prepared_metadata dict.
        if (rm_index(key) in indexed_keys):
            try:
                prepared_metadata[rm_index(key)][get_index(key)] = metadata[key]
            except IndexError:
                prepared_metadata[rm_index(key)].append(metadata[key])
        # If append is True, append value to source_metadata value.
        elif append_list and source_metadata.get(key):
            if metadata[key] in source_metadata[key]:
                continue
            if not isinstance(metadata[key], list):
                metadata[key] = [metadata[key]]
            if not isinstance(source_metadata[key], list):
                prepared_metadata[key] = [source_metadata[key]] + metadata[key]
            else:
                prepared_metadata[key] = source_metadata[key] + metadata[key]
        elif append and source_metadata.get(key):
            prepared_metadata[key] = '{0} {1}'.format(
                source_metadata[key], metadata[key])
        else:
            prepared_metadata[key] = metadata[key]

    # Remove values from metadata if value is REMOVE_TAG.
    _done = []
    for key in indexed_keys:
        # Filter None values from items with arrays as values
        prepared_metadata[key] = [v for v in prepared_metadata[key] if v]
        # Only filter the given indexed key if it has not already been
        # filtered.
        if key not in _done:
            indexes = []
            for k in metadata:
                if not get_index(k):
                    continue
                elif not rm_index(k) == key:
                    continue
                elif not metadata[k] == 'REMOVE_TAG':
                    continue
                else:
                    indexes.append(get_index(k))
            # Delete indexed values in reverse to not throw off the
            # subsequent indexes.
            for i in sorted(indexes, reverse=True):
                del prepared_metadata[key][i]
            _done.append(key)

    return prepared_metadata


def prepare_md_body(metadata, source_metadata, target, priority, append, append_list):
    priority = -5 if not priority else priority

    if 'metadata' in target:
        destination_metadata = source_metadata.copy()
        prepared_metadata = prepare_metadata(metadata, source_metadata, append,
                                             append_list)
        destination_metadata.update(prepared_metadata)
    elif 'files' in target:
        filename = '/'.join(target.split('/')[1:])
        for f in source_metadata:
            if f.get('name') == filename:
                source_metadata = f
                break
        destination_metadata = source_metadata.copy()
        prepared_metadata = prepare_metadata(metadata, source_metadata, append)
        destination_metadata.update(prepared_metadata)
    else:
        destination_metadata = source_metadata.copy()
        prepared_metadata = prepare_metadata(metadata, source_metadata, append)
        destination_metadata.update(prepared_metadata)

    # Delete metadata items where value is REMOVE_TAG.
    destination_metadata = dict(
        (k, v) for (k, v) in destination_metadata.items() if v != 'REMOVE_TAG'
    )

    patch = json.dumps(make_patch(source_metadata, destination_metadata).patch)

    data = {
        '-patch': patch,
        '-target': target,
        'priority': priority,
    }

    return data


def prepare_s3_headers(headers, metadata, queue_derive=True):
    """Convert a dictionary of metadata into S3 compatible HTTP
    headers, and append headers to ``headers``.

    :type metadata: dict
    :param metadata: Metadata to be converted into S3 HTTP Headers
                     and appended to ``headers``.

    :type headers: dict
    :param headers: (optional) S3 compatible HTTP headers.

    """
    if not metadata.get('scanner'):
        scanner = 'Internet Archive Python library {0}'.format(__version__)
        metadata['scanner'] = scanner
    prepared_metadata = prepare_metadata(metadata)

    headers['x-archive-auto-make-bucket'] = '1'
    if queue_derive is False:
        headers['x-archive-queue-derive'] = '0'
    else:
        headers['x-archive-queue-derive'] = '1'

    for meta_key, meta_value in prepared_metadata.items():
        # Encode arrays into JSON strings because Archive.org does not
        # yet support complex metadata structures in
        # <identifier>_meta.xml.
        if isinstance(meta_value, dict):
            meta_value = json.dumps(meta_value)
        # Convert the metadata value into a list if it is not already
        # iterable.
        if (isinstance(meta_value, six.string_types) or
                not hasattr(meta_value, '__iter__')):
            meta_value = [meta_value]
        # Convert metadata items into HTTP headers and add to
        # ``headers`` dict.
        for i, value in enumerate(meta_value):
            if not value:
                continue
            header_key = 'x-archive-meta{0:02d}-{1}'.format(i, meta_key)
            if (isinstance(value, six.string_types) and needs_quote(value)):
                if six.PY2 and isinstance(value, six.text_type):
                    value = value.encode('utf-8')
                value = 'uri({0})'.format(urllib.parse.quote(value))
            # because rfc822 http headers disallow _ in names, IA-S3 will
            # translate two hyphens in a row (--) into an underscore (_).
            header_key = header_key.replace('_', '--')
            headers[header_key] = value
    return headers


class FileReader:
    def __init__(self, fp):
        self.fp = fp

    def read_callback(self, size):
        try:
            return self.fp.read(size)
        except KeyboardInterrupt:
            sys.exit(130)
