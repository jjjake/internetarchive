import os
import re
from unittest.mock import patch

import pytest
import responses
from requests.exceptions import HTTPError, ReadTimeout

from internetarchive.exceptions import DirectoryTraversalError
from internetarchive.utils import sanitize_filename
from tests.conftest import DOWNLOAD_URL_RE, PROTOCOL, IaRequestsMock

EXPECTED_LAST_MOD_HEADER = {"Last-Modified": "Tue, 14 Nov 2023 20:25:48 GMT"}


def test_file_download_sanitizes_filename(tmpdir, nasa_item):
    tmpdir.chdir()

    # Mock is_windows to return True to test Windows-style sanitization
    with patch('internetarchive.utils.is_windows', return_value=True):
        with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(
                responses.GET,
                DOWNLOAD_URL_RE,
                body='test content',
                adding_headers=EXPECTED_LAST_MOD_HEADER,
            )
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
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test content',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir))
        assert 'cnt=0' in rsps.calls[-1].request.url


def test_file_download_count_views_true_omits_cnt(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test content',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir), count_views=True)
        assert 'cnt=' not in rsps.calls[-1].request.url


def test_file_download_user_params_override_default_cnt(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test content',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir), params={'cnt': 'x'})
        url = rsps.calls[-1].request.url
        assert 'cnt=x' in url
        assert 'cnt=0' not in url


def test_item_download_count_views_propagates(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test content',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        nasa_item.download(
            files=['nasa_meta.xml'], destdir=str(tmpdir), count_views=True
        )
        assert 'cnt=' not in rsps.calls[-1].request.url


def test_file_download_sends_range_header(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        file_obj = nasa_item.get_file('nasa_meta.xml')
        file_obj.download(destdir=str(tmpdir), headers={'Range': 'bytes=0-3'})
        assert rsps.calls[-1].request.headers.get('Range') == 'bytes=0-3'


def test_item_download_headers_propagate(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        nasa_item.download(
            files=['nasa_meta.xml'], destdir=str(tmpdir), headers={'Range': 'bytes=0-3'}
        )
        assert rsps.calls[-1].request.headers.get('Range') == 'bytes=0-3'


def test_item_download_range_jobs_no_separator(nasa_item, capfd):
    """Range segments are concatenated raw to stdout -- no ORS between them, so
    e.g. gzip members stay byte-adjacent."""
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='AAAA')
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='BBBB')
        nasa_item.download(
            range_jobs=[('nasa_meta.xml', 'bytes=0-3'), ('nasa_meta.xml', 'bytes=5-9')],
            stdout=True,
        )
    out = capfd.readouterr().out
    assert out == 'AAAABBBB'  # no '\n' (or any) separator between segments


def test_item_download_range_jobs_sends_ranges_in_order(nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='AAAA')
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='BBBB')
        nasa_item.download(
            range_jobs=[('nasa_meta.xml', 'bytes=0-3'), ('nasa_meta.xml', 'bytes=5-9')],
            stdout=True,
        )
        ranges = [
            c.request.headers['Range']
            for c in rsps.calls
            if 'Range' in c.request.headers
        ]
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
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        # Body md5 != file_obj.md5; if resume fired this would raise
        # InvalidChecksumError. It must not.
        file_obj.download(destdir=str(tmpdir), headers={'Range': 'bytes=5-8'})

        # The user's Range was sent unchanged (not overwritten by an auto-resume
        # ``bytes=<localsize>-`` header)...
        assert rsps.calls[-1].request.headers.get('Range') == 'bytes=5-8'

    # ...and the file was truncated + rewritten ('wb'), not appended to ('rb+').
    with open(local_path) as fh:
        assert fh.read() == 'test'


def test_range_not_satisfiable_fails_fast(tmpdir, nasa_item):
    """A 416 (Range Not Satisfiable) is permanent: it must not be retried, and
    with ignore_errors it returns False rather than raising."""
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            status=416,
            adding_headers={'Content-Range': 'bytes */7105'},
        )
        result = file_obj.download(
            destdir=str(tmpdir),
            ignore_errors=True,
            headers={'Range': 'bytes=99999999-'},
        )
        assert result is False
        # Exactly one request: the 416 was not retried.
        assert len(rsps.calls) == 1


def test_range_not_satisfiable_raises_without_ignore_errors(tmpdir, nasa_item):
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            status=416,
            adding_headers={'Content-Range': 'bytes */7105'},
        )
        with pytest.raises(HTTPError):
            file_obj.download(destdir=str(tmpdir), headers={'Range': 'bytes=99999999-'})
        assert len(rsps.calls) == 1


def test_stdout_ignores_local_file_no_resume_or_skip(tmpdir, nasa_item, capfd):
    """A stdout download must never consult the local filesystem: no skip,
    no auto-resume seek/append, regardless of a same-named local file.

    A same-named local file whose size differs from the remote size is what
    normally triggers the auto-resume path (and seeking a pipe would fail).
    """
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')
    with open(os.path.join(str(tmpdir), 'nasa_meta.xml'), 'w') as fh:
        fh.write('AA')
    assert len('AA') != file_obj.size

    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        file_obj.download(stdout=True)
        # No auto-resume Range header was sent for the stdout download...
        assert 'Range' not in rsps.calls[-1].request.headers

    # ...and the full body went to stdout (not skipped, not appended locally).
    assert capfd.readouterr().out == 'test'


def test_stdout_retry_writes_to_stdout_not_local_file(
    tmpdir, nasa_item, capfd, monkeypatch
):
    """A retried stdout download must keep writing to stdout, never fall back to
    creating a local disk file (which would leave the pipe empty).

    The first request raises a caught error to drive File.download's own retry
    loop (the ``retrying`` path); the retry then streams the body.
    """
    monkeypatch.setattr('internetarchive.files.sleep', lambda s: None)
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')

    class _Resp:
        def __init__(self, chunks):
            self._chunks = chunks
            self.headers = {}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield from self._chunks

    seq = [ReadTimeout('boom'), _Resp([b'test'])]

    def fake_get(url, **kwargs):
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(file_obj.item.session, 'get', fake_get)

    result = file_obj.download(stdout=True, retries=1)

    assert result is True
    # The body reached stdout on the retry...
    assert capfd.readouterr().out == 'test'
    # ...and no local file was created as a side effect of the retry.
    assert not os.path.exists(os.path.join(str(tmpdir), 'nasa_meta.xml'))


def test_resume_retry_recomputes_range_from_current_size(
    tmpdir, nasa_item, monkeypatch
):
    """On a retried auto-resume, the internal Range header must track the (grown)
    local file size so it stays aligned with the seek offset. A stale Range from
    the previous attempt would re-fetch already-written bytes and corrupt the file.
    """
    monkeypatch.setattr('internetarchive.files.sleep', lambda s: None)
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')
    local = os.path.join(str(tmpdir), 'nasa_meta.xml')
    with open(local, 'wb') as fh:
        fh.write(b'X' * 100)  # partial; remote size differs -> triggers resume
    assert file_obj.size != 100

    sent_ranges = []

    class _Resp:
        def __init__(self, chunks, exc=None):
            self._chunks = chunks
            self._exc = exc
            self.headers = {}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield from self._chunks
            if self._exc:
                raise self._exc

    seq = [
        _Resp([b'ABCDE'], exc=ReadTimeout('boom')),  # writes 5 bytes then fails
        _Resp([b'rest-of-data']),  # completes (checksum fails)
    ]

    def fake_get(url, **kwargs):
        sent_ranges.append(kwargs['headers'].get('Range'))
        return seq.pop(0)

    monkeypatch.setattr(file_obj.item.session, 'get', fake_get)

    # ignore_errors so the final (expected) checksum mismatch returns False
    # rather than raising; we only care about the Range headers that were sent.
    file_obj.download(destdir=str(tmpdir), retries=1, ignore_errors=True)

    # Attempt 1 resumed from 100; after writing 5 bytes the local file is 105,
    # so the retry must request bytes=105- (not the stale bytes=100-).
    assert sent_ranges == ['bytes=100-', 'bytes=105-']


def test_lowercase_range_header_suppresses_resume(tmpdir, nasa_item, monkeypatch):
    """A caller-supplied lowercase 'range' header is still an explicit range and
    must suppress auto-resume -- it must not be clobbered by a
    bytes=<localsize>- resume header (the check is case-insensitive)."""
    monkeypatch.setattr('internetarchive.files.sleep', lambda s: None)
    tmpdir.chdir()
    file_obj = nasa_item.get_file('nasa_meta.xml')
    local = os.path.join(str(tmpdir), 'nasa_meta.xml')
    with open(local, 'wb') as fh:
        fh.write(b'X' * 100)  # partial -> would normally trigger auto-resume

    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            body='test',
            adding_headers=EXPECTED_LAST_MOD_HEADER,
        )
        file_obj.download(
            destdir=str(tmpdir), ignore_errors=True, headers={'range': 'bytes=5-8'}
        )
        # The caller's explicit (lowercase) range was sent unchanged on the first
        # request; no auto-resume bytes=100- header overrode it.
        range_vals = [
            v for k, v in rsps.calls[0].request.headers.items() if k.lower() == 'range'
        ]

    assert range_vals == ['bytes=5-8']


def test_range_jobs_forward_caller_headers(nasa_item):
    """Caller-supplied headers (e.g. If-Match) are merged with the per-job Range
    header and sent on each range request."""
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='AAAA')
        nasa_item.download(
            range_jobs=[('nasa_meta.xml', 'bytes=0-3')],
            headers={'If-Match': '"etag123"'},
            stdout=True,
        )
        req = rsps.calls[-1].request

    assert req.headers.get('Range') == 'bytes=0-3'
    assert req.headers.get('If-Match') == '"etag123"'


def test_range_jobs_surface_download_errors(nasa_item):
    """A failed range segment (ignore_errors=True -> File.download returns False)
    must be surfaced in the returned errors list, not silently dropped."""
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            DOWNLOAD_URL_RE,
            status=416,
            adding_headers={'Content-Range': 'bytes */7105'},
        )
        errors = nasa_item.download(
            range_jobs=[('nasa_meta.xml', 'bytes=99999999-')],
            stdout=True,
            ignore_errors=True,
        )

    assert errors == ['nasa_meta.xml']
