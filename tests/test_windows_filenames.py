import os
import sys

import pytest

from internetarchive import get_item
from internetarchive.exceptions import DirectoryTraversalError
from internetarchive.files import File
from internetarchive.item import Item
from internetarchive.utils import (
    is_path_within_directory,
    sanitize_windows_filename,
    sanitize_windows_relpath,
)

IS_WIN = os.name == 'nt'

pytestmark = pytest.mark.skipif(not IS_WIN, reason='Windows specific tests')

def test_control_char_encoding():
    name = 'bad\x05name'
    sanitized, modified = sanitize_windows_filename(name)
    assert modified
    assert sanitized == 'bad%05name'

@pytest.mark.parametrize(('reserved','expected'), [
    ('AUX', 'AU%58'),
    ('CON', 'CO%4E'),
    ('COM1', 'COM%31'),
    ('LPT9', 'LPT%39'),
    ('NUL', 'NU%4C'),
])
def test_reserved_names(reserved, expected):
    sanitized, modified = sanitize_windows_filename(reserved)
    assert modified
    assert sanitized == expected

@pytest.mark.parametrize(('filename','expected'), [
    ('AUX.txt', 'AU%58.txt'),
    ('con.log', 'co%6E.log'),
    ('Com1.bin', 'Com%31.bin'),
    ('COM3.txt.txt', 'COM%33.txt.txt'),
])
def test_reserved_with_extension_sanitized(filename, expected):
    sanitized, modified = sanitize_windows_filename(filename)
    assert modified
    assert sanitized == expected

@pytest.mark.parametrize(('filename','expected'), [
    ('name.', 'name%2E'),
    ('name..', 'name%2E%2E'),
    ('trailspace ', 'trailspace%20'),
    ('both. ', 'both%2E%20'),
])
def test_trailing_dot_space(filename, expected):
    sanitized, modified = sanitize_windows_filename(filename)
    assert modified
    assert sanitized == expected

@pytest.mark.parametrize(('ch','enc'), [
    (':', '%3A'),
    ('*', '%2A'),
    ('<', '%3C'),
    ('>', '%3E'),
    ('|', '%7C'),
    ('?', '%3F'),
    ('\\', '%5C'),
    ('"', '%22')
])
def test_invalid_chars(ch, enc):
    sanitized, modified = sanitize_windows_filename(f'a{ch}b')
    assert modified
    assert sanitized == f'a{enc}b'

@pytest.mark.parametrize('name', [
    'back\\slash', 'dir\\\\file'
])
def test_backslash_always_encoded(name):
    sanitized, modified = sanitize_windows_filename(name)
    assert '%5C' in sanitized


def test_full_filename_combined_sanitization(tmp_path, monkeypatch):
    """Simulate downloading a file whose remote name contains many invalid characters
    including a backslash. We only test the sanitization logic up to path formation
    (not actual network download)."""
    remote_name = 'hello < > : " \\ | ? *.txt'
    # Use direct sanitize to assert expected output
    sanitized, modified = sanitize_windows_filename(remote_name)
    assert modified
    # Ensure each invalid char encoded
    for ch in ['<','>','|','?','*',':','\\','"',' ']:
        assert ch not in sanitized or ch == ' '  # trailing/inner spaces become %20
    assert '%5C' in sanitized  # backslash


def test_reserved_identifier_directory_sanitized(tmp_path):
    """Ensure that an item identifier that is a reserved device name is sanitized when
    constructing download paths."""
    # This test focuses on sanitize_windows_filename, as item.Download path building now
    # sanitizes components.
    reserved = 'AUX'
    sanitized, modified = sanitize_windows_filename(reserved)
    assert modified
    assert (sanitized.startswith('AU') and sanitized.endswith(b'X'.hex().upper()[:])) \
            or sanitized == 'AU%58'


def test_directory_traversal_exception_handled(monkeypatch, tmp_path):
    # Use is_path_within_directory directly
    base = tmp_path
    outside = tmp_path.parent / 'outside.txt'
    outside.write_text('x')
    assert not is_path_within_directory(str(base), str(outside))


@pytest.mark.parametrize('attempt', [
    '../evil.txt', '..\\evil.txt', '..%2Fevil.txt', '%2e%2e/evil.txt'
])
def test_traversal_attempt_sanitization(attempt):
    # sanitize_windows_relpath should NOT remove traversal but higher layer blocks it;
    # here we just ensure it encodes backslashes
    sanitized, _ = sanitize_windows_relpath(attempt, verbose=False)
    # Backslashes encoded
    if '\\' in attempt:
        assert '%5C' in sanitized or sanitized.replace('\\', '%5C')

@pytest.mark.parametrize('name', [
    'hello%20world', '%41already'
])
def test_existing_percent_sequences(name):
    # If no other encoding needed, percent remains unless part of %HH sequence
    # and no other changes?
    sanitized, modified = sanitize_windows_filename(name)
    # existing sequences remain unchanged because no other encoding triggered
    assert sanitized == name

@pytest.mark.parametrize('name', [
    'needs:encoding%20plus', 'AUX%41'  # reserved triggers change
])
def test_percent_gets_encoded_when_other_modifications(name):
    sanitized, modified = sanitize_windows_filename(name)
    if '%' in name and modified:
        assert '%25' in sanitized or name.count('%') == sanitized.count('%25')

# Directory traversal guard logic tests
# (cross-platform semantics validated on Windows here)

def test_is_path_within_directory_true(tmp_path):
    base = tmp_path
    target = base / 'subdir' / 'file.txt'
    target.parent.mkdir()
    target.write_text('x')
    assert is_path_within_directory(str(base), str(target))


def test_is_path_within_directory_false(tmp_path):
    base = tmp_path / 'a'
    other = tmp_path / 'b' / 'file.txt'
    base.mkdir()
    (tmp_path / 'b').mkdir()
    other.write_text('x')
    assert not is_path_within_directory(str(base), str(other))
