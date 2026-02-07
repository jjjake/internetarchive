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


def test_file_download_progress_callback(tmpdir, nasa_item):
    tmpdir.chdir()
    body = b'x' * 4096
    received_sizes = []

    def callback(size):
        received_sizes.append(size)

    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body=body,
                 adding_headers=EXPECTED_LAST_MOD_HEADER)
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(
            file_path='nasa_meta.xml',
            destdir=str(tmpdir),
            progress_callback=callback,
        )
    assert sum(received_sizes) == len(body)
    assert all(s > 0 for s in received_sizes)


def test_file_download_prevents_directory_traversal(tmpdir, nasa_item):
    tmpdir.chdir()
    # Don't mock the request since it won't be made due to the security check
    with IaRequestsMock(assert_all_requests_are_fired=False):
        # Test directory traversal attempt by getting the file and calling download directly
        file_obj = nasa_item.get_file('nasa_meta.xml')
        malicious_path = os.path.join('..', 'nasa_meta.xml')
        with pytest.raises(DirectoryTraversalError, match=r"outside.*directory"):
            file_obj.download(file_path=malicious_path, destdir=str(tmpdir))
