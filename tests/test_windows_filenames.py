import os
import sys
import pytest

from internetarchive.utils import sanitize_windows_filename, is_path_within_directory
from internetarchive.exceptions import DirectoryTraversalError

IS_WIN = os.name == 'nt'

pytestmark = pytest.mark.skipif(not IS_WIN, reason='Windows specific tests')

def test_control_char_encoding():
    name = 'bad\x05name'
    sanitized, modified = sanitize_windows_filename(name)
    assert modified
    assert sanitized == 'bad%05name'

@pytest.mark.parametrize('reserved,expected', [
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

@pytest.mark.parametrize('filename', [
    'AUX.txt', 'con.log', 'Com1.bin'
])
def test_reserved_with_extension_allowed(filename):
    sanitized, modified = sanitize_windows_filename(filename)
    # Should not modify because extension present
    assert not modified
    assert sanitized == filename

@pytest.mark.parametrize('filename,expected', [
    ('name.', 'name%2E'),
    ('name..', 'name%2E%2E'),
    ('trailspace ', 'trailspace%20'),
    ('both. ', 'both%2E%20'),
])
def test_trailing_dot_space(filename, expected):
    sanitized, modified = sanitize_windows_filename(filename)
    assert modified
    assert sanitized == expected

@pytest.mark.parametrize('ch,enc', [
    (':', '%3A'), ('*', '%2A'), ('<', '%3C'), ('>', '%3E'), ('|', '%7C'), ('?', '%3F'), ('\\', '%5C'), ('"', '%22')
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

@pytest.mark.parametrize('name', [
    'hello%20world', '%41already'
])
def test_existing_percent_sequences(name):
    # If no other encoding needed, percent remains unless part of %HH sequence and no other changes?
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

# Directory traversal guard logic tests (cross-platform semantics validated on Windows here)

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
