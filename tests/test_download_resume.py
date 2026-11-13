"""Offline regressions for retrying downloads of partial local files."""

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from requests import Response
from requests.exceptions import ReadTimeout

from internetarchive.files import File

CONTENT = b'complete file contents'


@pytest.fixture
def download_file(monkeypatch):
    """Create a file with synthetic metadata and a session that cannot use HTTP."""
    monkeypatch.setattr('internetarchive.files.sleep', lambda seconds: None)
    session = Mock(
        protocol='https:', host='archive.example', access_key=None, secret_key=None
    )
    item = SimpleNamespace(
        item_metadata={'metadata': {'identifier': 'offline-test'}}, session=session
    )
    return File(
        item,
        'sample.bin',
        file_metadata={
            'size': str(len(CONTENT)),
            'md5': md5(CONTENT).hexdigest(),
            'mtime': '1700000000',
        },
    )


def response(body, status):
    """Use requests' real streaming implementation with an in-memory body."""
    result = Response()
    result.status_code = status
    result.raw = BytesIO(body)
    return result


def test_resume_checksum_failure_retries_without_stale_range(tmp_path, download_file):
    """A rejected partial file must be retried as a fresh full download."""
    local_path = tmp_path / download_file.name
    local_path.write_bytes(b'bad')
    session = download_file.item.session
    session.get.side_effect = [
        response(CONTENT[3:], 206),
        response(CONTENT, 200),
    ]
    headers = {'X-Test': 'preserved'}

    assert download_file.download(destdir=str(tmp_path), retries=1, headers=headers)

    assert local_path.read_bytes() == CONTENT
    assert [call.kwargs['headers'] for call in session.get.call_args_list] == [
        {'X-Test': 'preserved', 'Range': 'bytes=3-'},
        {'X-Test': 'preserved'},
    ]
    assert headers == {'X-Test': 'preserved'}


@pytest.mark.parametrize('received', [4, len(CONTENT) - 3])
def test_resume_retry_rechecks_current_file_size(tmp_path, download_file, received):
    """Keep a growing partial file, but drop resume state once it is complete."""
    local_path = tmp_path / download_file.name
    local_path.write_bytes(CONTENT[:3])

    def interrupted_content(chunk_size):
        yield CONTENT[3 : 3 + received]
        raise ReadTimeout('interrupted after writing bytes')

    interrupted = response(b'', 206)
    interrupted.iter_content = interrupted_content
    offset = 3 + received
    complete = offset == len(CONTENT)
    session = download_file.item.session
    session.get.side_effect = [
        interrupted,
        response(CONTENT if complete else CONTENT[offset:], 200 if complete else 206),
    ]

    assert download_file.download(destdir=str(tmp_path), retries=1)

    assert local_path.read_bytes() == CONTENT
    assert [
        call.kwargs['headers'].get('Range') for call in session.get.call_args_list
    ] == [
        'bytes=3-',
        None if complete else f'bytes={offset}-',
    ]


@pytest.mark.parametrize('range_header', ['Range', 'range'])
def test_explicit_range_is_preserved_on_retry(tmp_path, download_file, range_header):
    """Retry a caller's intentional byte range without enabling automatic resume."""
    local_path = tmp_path / download_file.name
    local_path.write_bytes(b'bad')
    session = download_file.item.session
    session.get.side_effect = [ReadTimeout('interrupted'), response(CONTENT[3:7], 206)]
    headers = {range_header: 'bytes=3-6', 'X-Test': 'preserved'}

    assert download_file.download(destdir=str(tmp_path), retries=1, headers=headers)

    assert local_path.read_bytes() == CONTENT[3:7]
    assert [call.kwargs['headers'] for call in session.get.call_args_list] == [
        headers,
        headers,
    ]
    assert headers == {range_header: 'bytes=3-6', 'X-Test': 'preserved'}
