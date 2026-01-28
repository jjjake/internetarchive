import string
import warnings
from unittest.mock import patch

import pytest

import internetarchive.utils
from tests.conftest import NASA_METADATA_PATH, IaRequestsMock


def test_utils():
    with open(__file__, encoding='utf-8') as fh:
        list(internetarchive.utils.chunk_generator(fh, 10))

    ifp = internetarchive.utils.IterableToFileAdapter([1, 2], 200)
    assert len(ifp) == 200
    ifp.read()


def test_needs_quote():
    notascii = ('ȧƈƈḗƞŧḗḓ ŧḗẋŧ ƒǿř ŧḗşŧīƞɠ, ℛℯα∂α♭ℓℯ ♭ʊ☂ η☺т Ѧ$☾ℐℐ, '
                '¡ooʇ ןnɟǝsn sı uʍop-ǝpısdn')
    assert internetarchive.utils.needs_quote(notascii)
    assert internetarchive.utils.needs_quote(string.whitespace)
    assert not internetarchive.utils.needs_quote(string.ascii_letters + string.digits)


def test_validate_s3_identifier():
    id1 = 'valid-Id-123-_foo'
    id2 = '!invalid-Id-123-_foo'
    id3 = 'invalid-Id-123-_foo+bar'
    id4 = 'invalid-Id-123-_føø'
    id5 = 'i'

    valid = internetarchive.utils.validate_s3_identifier(id1)
    assert valid

    for invalid_id in [id2, id3, id4, id5]:
        try:
            internetarchive.utils.validate_s3_identifier(invalid_id)
        except Exception as exc:
            assert isinstance(exc, internetarchive.utils.InvalidIdentifierException)


def test_get_md5():
    with open(__file__, 'rb') as fp:
        md5 = internetarchive.utils.get_md5(fp)
    assert isinstance(md5, str)


def test_IdentifierListAsItems(session):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        it = internetarchive.utils.IdentifierListAsItems('nasa', session)
        assert it[0].identifier == 'nasa'
        assert it.nasa.identifier == 'nasa'


def test_IdentifierListAsItems_len(session):
    assert len(internetarchive.utils.IdentifierListAsItems(['foo', 'bar'], session)) == 2

# TODO: Add test of slice access to IdenfierListAsItems


def test_get_s3_xml_text():
    xml_str = ('<Error><Code>NoSuchBucket</Code>'
               '<Message>The specified bucket does not exist.</Message>'
               '<Resource>'
               'does-not-exist-! not found by Metadata::get_obj()[server]'
               '</Resource>'
               '<RequestId>d56bdc63-169b-4b4f-8c47-0fac6de39040</RequestId></Error>')

    expected_txt = internetarchive.utils.get_s3_xml_text(xml_str)
    assert expected_txt == ('The specified bucket does not exist. - does-not-exist-! '
                            'not found by Metadata::get_obj()[server]')


def test_get_file_size():
    try:
        s = internetarchive.utils.get_file_size(NASA_METADATA_PATH)
    except AttributeError as exc:
        assert "object has no attribute 'seek'" in str(exc)
    with open(NASA_METADATA_PATH) as fp:
        s = internetarchive.utils.get_file_size(fp)
    assert s == 7557


def test_is_valid_metadata_key():
    # Keys starting with "xml" should also be invalid
    # due to the XML specification, but are supported
    # by the Internet Archive.
    valid = ('adaptive_ocr', 'bookreader-defaults', 'frames_per_second',
             'identifier', 'possible-copyright-status', 'index[0]')
    invalid = ('Analog Format', "Date of transfer (probably today's date)",
               '_metadata_key', '58', '_', '<invalid>', 'a')

    for metadata_key in valid:
        assert internetarchive.utils.is_valid_metadata_key(metadata_key)

    for metadata_key in invalid:
        assert not internetarchive.utils.is_valid_metadata_key(metadata_key)


def test_is_windows():
    with patch('platform.system', return_value='Windows'), \
         patch('sys.platform', 'win32'):
        assert internetarchive.utils.is_windows() is True

    with patch('platform.system', return_value='Linux'), \
         patch('sys.platform', 'linux'):
        assert internetarchive.utils.is_windows() is False

def test_sanitize_filename_windows():
    test_cases = [
        ('file:name.txt', 'file%3Aname.txt'),
        ('file%name.txt', 'file%25name.txt'),
        ('con.txt', 'con.txt'),  # Reserved name, but no invalid chars so unchanged
        ('file .txt', 'file .txt'),  # Internal space preserved (not trailing)
        ('file  ', 'file'),  # Trailing spaces removed
        ('file..', 'file'),  # Trailing dots removed
        ('file . ', 'file'),  # Trailing space and dot removed
    ]

    for input_name, expected in test_cases:
        result = internetarchive.utils.sanitize_filename_windows(input_name)
        assert result == expected


def test_sanitize_filename_posix():
    # Test without colon encoding
    result = internetarchive.utils.sanitize_filename_posix('file/name.txt', False)
    assert result == 'file%2Fname.txt'

    # Test with colon encoding
    result = internetarchive.utils.sanitize_filename_posix('file:name.txt', True)
    assert result == 'file%3Aname.txt'

    # Test mixed encoding
    result = internetarchive.utils.sanitize_filename_posix('file/:name.txt', True)
    assert result == 'file%2F%3Aname.txt'


def test_unsanitize_filename():
    test_cases = [
        ('file%3Aname.txt', 'file:name.txt'),
        ('file%2Fname.txt', 'file/name.txt'),
        ('file%25name.txt', 'file%name.txt'),  # Percent sign
        ('normal.txt', 'normal.txt'),  # No encoding
    ]

    for input_name, expected in test_cases:
        with warnings.catch_warnings(record=True) as w:
            result = internetarchive.utils.unsanitize_filename(input_name)
            assert result == expected
            if '%' in input_name:
                assert len(w) == 1
                assert issubclass(w[0].category, UserWarning)


def test_sanitize_filename():
    # Test Windows path
    with patch('internetarchive.utils.is_windows', return_value=True):
        with warnings.catch_warnings(record=True) as w:
            result = internetarchive.utils.sanitize_filename('file:name.txt')
            assert result == 'file%3Aname.txt'
            assert len(w) == 1
            assert "sanitized" in str(w[0].message)

    # Test POSIX path
    with patch('internetarchive.utils.is_windows', return_value=False):
        result = internetarchive.utils.sanitize_filename('file/name.txt', False)
        assert result == 'file%2Fname.txt'


def test_sanitize_filepath():
    # Test with colon encoding
    result = internetarchive.utils.sanitize_filepath('/path/to/file:name.txt', True)
    assert result == '/path/to/file%3Aname.txt'

    # Test without colon encoding
    result = internetarchive.utils.sanitize_filepath('/path/to/file:name.txt', False)
    assert result == '/path/to/file:name.txt'  # Colon not encoded on POSIX by default

    # Test Windows path (mocked)
    with patch('internetarchive.utils.is_windows', return_value=True):
        result = internetarchive.utils.sanitize_filepath('/path/to/con.txt')
        assert result == '/path/to/con.txt'  # Reserved name sanitized


class MockPreparedRequest:
    """Mock requests.PreparedRequest for testing request_to_curl."""
    def __init__(self, method='GET', url='https://example.com', headers=None, body=None):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.body = body


def test_request_to_curl_basic():
    """Test basic curl command generation."""
    request = MockPreparedRequest(
        method='GET',
        url='https://archive.org/metadata/test',
        headers={'User-Agent': 'test-agent', 'Accept': '*/*'},
    )
    curl = internetarchive.utils.request_to_curl(request, redact_auth=False)

    assert curl.startswith('curl -X GET')
    assert 'https://archive.org/metadata/test' in curl
    assert "-H 'User-Agent: test-agent'" in curl
    assert "-H 'Accept: */*'" in curl


def test_request_to_curl_auth_redaction():
    """Test that sensitive headers are redacted."""
    request = MockPreparedRequest(
        method='GET',
        url='https://archive.org/metadata/test',
        headers={
            'Authorization': 'LOW access:secret',
            'Cookie': 'logged-in-user=test@example.com; logged-in-sig=abc123',
        },
    )

    # With redaction (default)
    curl_redacted = internetarchive.utils.request_to_curl(request, redact_auth=True)
    assert '[REDACTED]' in curl_redacted
    assert 'LOW access:secret' not in curl_redacted
    assert 'logged-in-user' not in curl_redacted

    # Without redaction
    curl_full = internetarchive.utils.request_to_curl(request, redact_auth=False)
    assert 'LOW access:secret' in curl_full
    assert 'logged-in-user=test@example.com' in curl_full


def test_request_to_curl_body_redaction():
    """Test that access/secret in body are redacted."""
    request = MockPreparedRequest(
        method='POST',
        url='https://archive.org/metadata/test',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        body='access=myaccesskey&secret=mysecretkey&data=value',
    )

    curl_redacted = internetarchive.utils.request_to_curl(request, redact_auth=True)
    assert 'access=[REDACTED]' in curl_redacted
    assert 'secret=[REDACTED]' in curl_redacted
    assert 'myaccesskey' not in curl_redacted
    assert 'mysecretkey' not in curl_redacted

    curl_full = internetarchive.utils.request_to_curl(request, redact_auth=False)
    assert 'myaccesskey' in curl_full
    assert 'mysecretkey' in curl_full


def test_request_to_curl_compressed():
    """Test that --compressed is added when Accept-Encoding is present."""
    request_with_encoding = MockPreparedRequest(
        method='GET',
        url='https://archive.org/metadata/test',
        headers={'Accept-Encoding': 'gzip, deflate'},
    )
    curl = internetarchive.utils.request_to_curl(request_with_encoding)
    assert '--compressed' in curl

    request_without_encoding = MockPreparedRequest(
        method='GET',
        url='https://archive.org/metadata/test',
        headers={},
    )
    curl = internetarchive.utils.request_to_curl(request_without_encoding)
    assert '--compressed' not in curl


def test_request_to_curl_binary_body():
    """Test handling of binary body data."""
    request = MockPreparedRequest(
        method='POST',
        url='https://archive.org/upload/test',
        headers={},
        body=b'\x00\x01\x02\xff\xfe',  # Non-UTF8 binary data
    )
    curl = internetarchive.utils.request_to_curl(request)
    assert '<binary data>' in curl
