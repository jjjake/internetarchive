# -*- coding: utf-8 -*-
import os
import sys
import string
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import six

import responses

import internetarchive.utils


protocol = 'https:'


def test_utils():
    list(internetarchive.utils.chunk_generator(open(__file__), 10))
    ifp = internetarchive.utils.IterableToFileAdapter([1, 2], 200)
    assert len(ifp) == 200
    ifp.read()


def test_needs_quote():
    notascii = ('ȧƈƈḗƞŧḗḓ ŧḗẋŧ ƒǿř ŧḗşŧīƞɠ, ℛℯα∂α♭ℓℯ ♭ʊ☂ η☺т Ѧ$☾ℐℐ, '
                '¡ooʇ ןnɟǝsn sı uʍop-ǝpısdn')
    assert internetarchive.utils.needs_quote(notascii)
    assert internetarchive.utils.needs_quote(string.whitespace)
    assert not internetarchive.utils.needs_quote(string.ascii_letters + string.digits)


def test_validate_ia_identifier():
    valid = internetarchive.utils.validate_ia_identifier('valid-Id-123-_foo')
    assert valid
    try:
        internetarchive.utils.validate_ia_identifier('!invalid-Id-123-_foo')
    except Exception as exc:
        assert isinstance(exc, AssertionError)


def test_get_md5():
    md5 = internetarchive.utils.get_md5(open(__file__, 'rb'))
    assert isinstance(md5, six.string_types)


def test_map2x():
    keys = ('first', 'second')
    columns = ('first', 'second')
    for key, value in internetarchive.utils.map2x(None, keys, columns):
        assert key == value
    for key, value in internetarchive.utils.map2x(lambda k, v: [k, v], keys, columns):
        assert key == value


@responses.activate
def test_IdentifierListAsItems(session, testitem_metadata):
    responses.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                  body=testitem_metadata,
                  status=200,
                  content_type='application/json')
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
    f = os.path.join(os.path.dirname(__file__), 'data/nasa_meta.json')
    try:
        s = internetarchive.utils.get_file_size(f)
    except AttributeError as exc:
        assert "object has no attribute 'seek'" in str(exc)
    s = internetarchive.utils.get_file_size(open(f))
    assert s == 7557
