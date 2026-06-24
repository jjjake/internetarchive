import os
import re
from unittest.mock import patch

import pytest
import responses

from internetarchive.exceptions import DirectoryTraversalError
from internetarchive.utils import sanitize_filename
from tests.conftest import PROTOCOL, IaRequestsMock

DOWNLOAD_URL_RE = re.compile(f'{PROTOCOL}//archive.org/download/.*')
EXPECTED_LAST_MOD_HEADER = {"Last-Modified": "Tue, 14 Nov 2023 20:25:48 GMT"}


def test_file_download_sanitizes_filename(tmpdir, nasa_item):
    tmpdir.chdir()

    # Mock is_windows to return True to test Windows-style sanitization
    with patch('internetarchive.utils.is_windows', return_value=True):
        with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, DOWNLOAD_URL_RE,
                     body='test content',
                     adding_headers=EXPECTED_LAST_MOD_HEADER)
            # Test filename with Windows-invalid characters
            file_obj = nasa_item.get_file('nasa_meta.xml')
            problematic_name = 'file:with<illegal>chars.xml'
            sanitized_name = sanitize_filename(problematic_name)
            expected_path = os.path.join(str(tmpdir), sanitized_name)

            file_obj.download(file_path=sanitized_name, destdir=str(tmpdir))
            assert os.path.exists(expected_path)


def test_file_download_prevents_directory_traversal(tmpdir, nasa_item):
    tmpdir.chdir()
    # Don't mock the request since it won't be made due to the security check
    with IaRequestsMock(assert_all_requests_are_fired=False):
        # Test directory traversal attempt by getting the file and calling download directly
        file_obj = nasa_item.get_file('nasa_meta.xml')
        malicious_path = os.path.join('..', 'nasa_meta.xml')
        with pytest.raises(DirectoryTraversalError, match=r"outside.*directory"):
            file_obj.download(file_path=malicious_path, destdir=str(tmpdir))


def test_file_download_sends_cnt_zero_by_default(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir))
        assert 'cnt=0' in rsps.calls[-1].request.url


def test_file_download_count_views_true_omits_cnt(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir), count_views=True)
        assert 'cnt=' not in rsps.calls[-1].request.url


def test_file_download_user_params_override_default_cnt(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir), params={'cnt': 'x'})
        url = rsps.calls[-1].request.url
        assert 'cnt=x' in url
        assert 'cnt=0' not in url


def test_item_download_count_views_propagates(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        nasa_item.download(files=['nasa_meta.xml'],
                           destdir=str(tmpdir),
                           count_views=True)
        assert 'cnt=' not in rsps.calls[-1].request.url


def test_file_download_sends_range_header(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir), headers={'Range': 'bytes=0-3'})
        assert rsps.calls[-1].request.headers.get('Range') == 'bytes=0-3'


def test_item_download_headers_propagate(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        nasa_item.download(files=['nasa_meta.xml'],
                           destdir=str(tmpdir),
                           headers={'Range': 'bytes=0-3'})
        assert rsps.calls[-1].request.headers.get('Range') == 'bytes=0-3'


def test_item_download_range_jobs_no_separator(nasa_item, capfd):
    """Range segments are concatenated raw to stdout -- no ORS between them, so
    e.g. gzip members stay byte-adjacent."""
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='AAAA')
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='BBBB')
        nasa_item.download(
            range_jobs=[('nasa_meta.xml', 'bytes=0-3'),
                        ('nasa_meta.xml', 'bytes=5-9')],
            stdout=True,
        )
    out = capfd.readouterr().out
    assert out == 'AAAABBBB'  # no '\n' (or any) separator between segments


def test_item_download_range_jobs_sends_ranges_in_order(nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='AAAA')
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='BBBB')
        nasa_item.download(
            range_jobs=[('nasa_meta.xml', 'bytes=0-3'),
                        ('nasa_meta.xml', 'bytes=5-9')],
            stdout=True,
        )
        ranges = [c.request.headers['Range']
                  for c in rsps.calls if 'Range' in c.request.headers]
        assert ranges == ['bytes=0-3', 'bytes=5-9']


def test_file_download_explicit_range_skips_resume(tmpdir, nasa_item):
    """An explicit Range must not trigger resume (seek/append) or the
    full-file checksum validation, even when a shorter local file exists.
    """
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')
    # Pre-create a partial local file whose size differs from the remote size,
    # which is what normally triggers the auto-resume code path.
    local_path = os.path.join(str(tmpdir), 'nasa_meta.xml')
    with open(local_path, 'w') as fh:
        fh.write('AAAA')
    assert len('AAAA') != file_obj.size

    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test',
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        # Body md5 != file_obj.md5; if resume fired this would raise
        # InvalidChecksumError. It must not.
        file_obj.download(destdir=str(tmpdir), headers={'Range': 'bytes=5-8'})

        # The user's Range was sent unchanged (not overwritten by an auto-resume
        # ``bytes=<localsize>-`` header)...
        assert rsps.calls[-1].request.headers.get('Range') == 'bytes=5-8'

    # ...and the file was truncated + rewritten ('wb'), not appended to ('rb+').
    with open(local_path) as fh:
        assert fh.read() == 'test'
