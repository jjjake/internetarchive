import string

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
