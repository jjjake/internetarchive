import hashlib
import os
import re
from itertools import starmap
from six.moves import zip_longest


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
        s.decode('ascii')
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


class IterableToFileAdapter(object):
    def __init__(self, iterable, size):
        self.iterator = iter(iterable)
        self.length = size

    def read(self, size=-1):  # TBD: add buffer for `len(data) > size` case
        return next(self.iterator, b'')

    def __len__(self):
        return self.length
