#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2022 Internet Archive
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

:copyright: (C) 2012-2022 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from collections.abc import Mapping
from typing import Iterable
from xml.dom.minidom import parseString

# Make preferred JSON package available via `from internetarchive.utils import json`
try:
    import ujson as json

    # ujson lacks a JSONDecodeError: https://github.com/ultrajson/ultrajson/issues/497
    JSONDecodeError = ValueError
except ImportError:
    import json  # type: ignore
    JSONDecodeError = json.JSONDecodeError  # type: ignore


def deep_update(d: dict, u: Mapping) -> dict:
    for k, v in u.items():
        if isinstance(v, Mapping):
            r = deep_update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


class InvalidIdentifierException(Exception):
    pass


def validate_s3_identifier(string: str) -> bool:
    legal_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-'
    # periods, underscores, and dashes are legal, but may not be the first
    # character!
    if any(string.startswith(c) is True for c in ['.', '_', '-']):
        raise InvalidIdentifierException('Identifier cannot begin with periods ".", underscores '
                                        '"_", or dashes "-".')

    if len(string) > 100 or len(string) < 3:
        raise InvalidIdentifierException('Identifier should be between 3 and 80 characters in '
                                        'length.')

    # Support for uploading to user items, e.g. first character can be `@`.
    if string.startswith('@'):
        string = string[1:]

    if any(c not in legal_chars for c in string):
        raise InvalidIdentifierException('Identifier can only contain alphanumeric characters, '
                                        'periods ".", underscores "_", or dashes "-". However, '
                                        'identifier cannot begin with periods, underscores, or '
                                        'dashes.')

    return True


def needs_quote(s: str) -> bool:
    try:
        s.encode('ascii')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return True
    return re.search(r'\s', s) is not None


def norm_filepath(fp: bytes | str) -> str:
    if isinstance(fp, bytes):
        fp = fp.decode('utf-8')
    fp = fp.replace(os.path.sep, '/')
    if not fp.startswith('/'):
        fp = f'/{fp}'
    return fp


def get_md5(file_object) -> str:
    m = hashlib.md5()
    while True:
        data = file_object.read(8192)
        if not data:
            break
        m.update(data)
    file_object.seek(0, os.SEEK_SET)
    return m.hexdigest()


def chunk_generator(fp, chunk_size: int):
    while True:
        chunk = fp.read(chunk_size)
        if not chunk:
            break
        yield chunk


def suppress_keyboard_interrupt_message() -> None:
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


class IterableToFileAdapter:
    def __init__(self, iterable, size: int, pre_encode: bool = False):
        self.iterator = iter(iterable)
        self.length = size
        # pre_encode is needed because http doesn't know that it
        # needs to encode a TextIO object when it's wrapped
        # in the Iterator from tqdm.
        # So, this FileAdapter provides pre-encoded output
        self.pre_encode = pre_encode

    def read(self, size: int = -1):  # TBD: add buffer for `len(data) > size` case
        if self.pre_encode:
            # this adapter is intended to emulate the encoding that is usually
            # done by the http lib.
            # As of 2022, iso-8859-1 encoding is used to meet the HTTP standard,
            # see in the cpython repo (https://github.com/python/cpython
            # Lib/http/client.py lines 246; 1340; or grep 'iso-8859-1'
            return next(self.iterator, '').encode("iso-8859-1")
        return next(self.iterator, b'')

    def __len__(self) -> int:
        return self.length


class IdentifierListAsItems:
    """This class is a lazily-loaded list of Items, accessible by index or identifier.
    """

    def __init__(self, id_list_or_single_id, session):
        self.ids = (id_list_or_single_id
                    if isinstance(id_list_or_single_id, list)
                    else [id_list_or_single_id])
        self._items = [None] * len(self.ids)
        self.session = session

    def __len__(self) -> int:
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

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.ids!r})'


def get_s3_xml_text(xml_str: str) -> str:
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
            return f'{_msg} - {_resource.strip()}'
        else:
            return _msg
    except Exception:
        return str(xml_str)


def get_file_size(file_obj) -> int | None:
    if is_filelike_obj(file_obj):
        try:
            file_obj.seek(0, os.SEEK_END)
            size = file_obj.tell()
            # Avoid OverflowError.
            if size > sys.maxsize:
                size = None
            file_obj.seek(0, os.SEEK_SET)
        except OSError:
            size = None
    else:
        st = os.stat(file_obj)
        size = st.st_size
    return size


def iter_directory(directory: str):
    """Given a directory, yield all files recursively as a two-tuple (filepath, s3key)"""
    for path, _dir, files in os.walk(directory):
        for f in files:
            filepath = os.path.join(path, f)
            key = os.path.relpath(filepath, directory)
            yield (filepath, key)


def recursive_file_count_and_size(files, item=None, checksum=False):
    """Given a filepath or list of filepaths, return the total number and size of files.
    If `checksum` is `True`, skip over files whose MD5 hash matches any file in the `item`.
    """
    if not isinstance(files, (list, set)):
        files = [files]
    total_files = 0
    total_size = 0
    if checksum is True:
        md5s = [f.get('md5') for f in item.files]
    else:
        md5s = []
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
            it = iter_directory(f)
        else:
            it = [(f, None)]
        for x, _ in it:
            if checksum is True:
                try:
                    with open(x, 'rb') as fh:
                        lmd5 = get_md5(fh)
                except TypeError:
                    # Support file-like objects.
                    lmd5 = get_md5(x)
                if lmd5 in md5s:
                    continue
            total_size += get_file_size(x)
            total_files += 1
    return total_files, total_size


def recursive_file_count(*args, **kwargs):
    """Like `recursive_file_count_and_size`, but returns only the file count."""
    total_files, _ = recursive_file_count_and_size(*args, **kwargs)
    return total_files


def is_dir(obj) -> bool:
    """Special is_dir function to handle file-like object cases that
    cannot be stat'd"""
    try:
        return os.path.isdir(obj)
    except TypeError as exc:
        return False


def is_filelike_obj(obj) -> bool:
    """Distinguish file-like from path-like objects"""
    try:
        os.fspath(obj)
    except TypeError:
        return True
    else:
        return False


def reraise_modify(
    caught_exc: Exception,
    append_msg: str,
    prepend: bool = False,
) -> None:
    """Append message to exception while preserving attributes.

    Preserves exception class, and exception traceback.

    Note:
        This function needs to be called inside an except because an exception
        must be active in the current scope.

    Args:
        caught_exc(Exception): The caught exception object
        append_msg(str): The message to append to the caught exception
        prepend(bool): If True prepend the message to args instead of appending

    Returns:
        None

    Side Effects:
        Re-raises the exception with the preserved data / trace but
        modified message
    """
    if not caught_exc.args:
        # If no args, create our own tuple
        arg_list = [append_msg]
    else:
        # Take the last arg
        # If it is a string
        # append your message.
        # Otherwise append it to the
        # arg list(Not as pretty)
        arg_list = list(caught_exc.args[:-1])
        last_arg = caught_exc.args[-1]
        if isinstance(last_arg, str):
            if prepend:
                arg_list.append(append_msg + last_arg)
            else:
                arg_list.append(last_arg + append_msg)
        else:
            arg_list += [last_arg, append_msg]
    caught_exc.args = tuple(arg_list)
    raise


def remove_none(obj):
    if isinstance(obj, (list, tuple, set)):
        lst = type(obj)(remove_none(x) for x in obj if x)
        try:
            return [dict(t) for t in {tuple(sorted(d.items())) for d in lst}]
        except (AttributeError, TypeError):
            return lst
    elif isinstance(obj, dict):
        return type(obj)((remove_none(k), remove_none(v))
                         for k, v in obj.items() if k is not None and v is not None)
    else:
        return obj


def delete_items_from_dict(d: dict | list, to_delete):
    """Recursively deletes items from a dict,
    if the item's value(s) is in ``to_delete``.
    """
    if not isinstance(to_delete, list):
        to_delete = [to_delete]
    if isinstance(d, dict):
        for single_to_delete in set(to_delete):
            if single_to_delete in d.values():
                for k, v in d.copy().items():
                    if v == single_to_delete:
                        del d[k]
        for v in d.values():
            delete_items_from_dict(v, to_delete)
    elif isinstance(d, list):
        for i in d:
            delete_items_from_dict(i, to_delete)
    return remove_none(d)


def is_valid_metadata_key(name: str) -> bool:
    # According to the documentation a metadata key
    # has to be a valid XML tag name.
    #
    # The actual allowed tag names (at least as tested with the metadata API),
    # are way more restrictive and only allow ".-A-Za-z_", possibly followed
    # by an index in square brackets e. g. [0].
    # On the other hand the Archive allows tags starting with the string "xml".
    return bool(re.fullmatch(r'[A-Za-z][.\-0-9A-Za-z_]+(?:\[[0-9]+\])?', name))


def merge_dictionaries(
    dict0: dict,
    dict1: dict,
    keys_to_drop: Iterable | None = None,
) -> dict:
    """Merge two dictionaries.

       Items in `dict0` can optionally be dropped before the merge.

       If equal keys exist in both dictionaries,
       entries in`dict0` are overwritten.

       :param dict0: A base dictionary with the bulk of the items.

       :param dict1: Additional items which overwrite the items in `dict0`.

       :param keys_to_drop: An iterable of keys to drop from `dict0` before the merge.

       :returns: A merged dictionary.
       """
    new_dict = dict0.copy()
    if keys_to_drop is not None:
        for key in keys_to_drop:
            new_dict.pop(key, None)
    # Items from `dict1` take precedence over items from `dict0`.
    new_dict.update(dict1)
    return new_dict


def parse_dict_cookies(value: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for item in value.split(';'):
        item = item.strip()
        if not item:
            continue
        if '=' not in item:
            result[item] = None
            continue
        name, value = item.split('=', 1)
        result[name] = value
    if 'domain' not in result:
        result['domain'] = '.archive.org'
    if 'path' not in result:
        result['path'] = '/'
    return result
