# -*- coding: utf-8 -*-
import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import json

import responses

from internetarchive.cli import ia


protocol = 'https:'


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')

with open(TEST_JSON_FILE, 'r') as fh:
    ITEM_METADATA = fh.read().strip()
with open(os.path.join(ROOT_DIR, 'tests/data/s3_status_check.json'), 'r') as fh:
    STATUS_CHECK_RESPONSE = fh.read().strip()


def test_ia_upload(tmpdir):
    tmpdir.chdir()
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT, '{0}//s3.us.archive.org/nasa/test.txt'.format(protocol),
                 body='',
                 status=200,
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'test.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    with open('internetarchive.log', 'r') as fh:
        assert ('uploaded test.txt to {0}//s3.us.archive.org/nasa/'
                'test.txt'.format(protocol)) in fh.read()


def test_ia_upload_status_check(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//s3.us.archive.org'.format(protocol),
                 body=STATUS_CHECK_RESPONSE,
                 status=200,
                 content_type='application/json')

        sys.argv = ['ia', 'upload', 'nasa', '--status-check']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

        out, err = capsys.readouterr()
        assert 'success: nasa is accepting requests.' in out

        j = json.loads(STATUS_CHECK_RESPONSE)
        j['over_limit'] = 1
        rsps.add(responses.GET, '{0}//s3.us.archive.org'.format(protocol),
                 body=json.dumps(j),
                 status=200,
                 content_type='application/json')

        sys.argv = ['ia', 'upload', 'nasa', '--status-check']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 1

        out, err = capsys.readouterr()
        assert ('warning: nasa is over limit, and not accepting requests. '
                'Expect 503 SlowDown errors.') in err


def test_ia_upload_debug(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        sys.argv = ['ia', 'upload', '--debug', 'nasa', 'test.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    print(set(out.split('\n')))
    assert set(out.split('\n')) == set([
        '',
        'Endpoint:',
        ' {0}//s3.us.archive.org/nasa/test.txt'.format(protocol),
        'HTTP Headers:',
        ' x-archive-size-hint:3',
        'nasa:'])


def test_ia_upload_403(capsys):
    s3_error = ('<Error>'
                '<Code>SignatureDoesNotMatch</Code>'
                '<Message>The request signature we calculated does not match '
                'the signature you provided. Check your AWS Secret Access Key '
                'and signing method. For more information, see REST '
                'Authentication and SOAP Authentication for details.</Message>'
                "<Resource>'PUT\n\n\n\n/iacli-test-item60/test-replace.txt'</Resource>"
                '<RequestId>18a9c5ea-088f-42f5-9fcf-70651cc085ca</RequestId>'
                '</Error>')

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT,
                 '{0}//s3.us.archive.org/nasa/test_ia_upload.py'.format(protocol),
                 body=s3_error,
                 status=403,
                 content_type='text/plain')
        sys.argv = ['ia', 'upload', 'nasa', __file__]
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 1

    out, err = capsys.readouterr()
    assert 'error uploading test_ia_upload.py' in err


def test_ia_upload_invalid_cmd(capsys):
    sys.argv = ['ia', 'upload', 'nasa', 'nofile.txt']
    try:
        ia.main()
    except SystemExit as exc:
        assert exc.code == 1

    out, err = capsys.readouterr()
    assert '<file> should be a readable file or directory.' in err


def test_ia_upload_size_hint(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        sys.argv = ['ia', 'upload', '--debug', 'nasa', '--size-hint', '30', 'test.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    assert set(out.split('\n')) == set(['', ' x-archive-size-hint:30',
                                        'Endpoint:', 'HTTP Headers:', 'nasa:',
                                        (' {0}//s3.us.archive.org/nasa/'
                                         'test.txt'.format(protocol))])


def test_ia_upload_unicode(tmpdir):
    tmpdir.chdir()
    with open('தமிழ் - baz ∆.txt', 'w') as fh:
        fh.write('unicode foo')
    fname = u'தமிழ் - foo; baz ∆.txt'
    efname = '%E0%AE%A4%E0%AE%AE%E0%AE%BF%E0%AE%B4%E0%AF%8D%20-%20baz%20%E2%88%86.txt'
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT,
                 '{0}//s3.us.archive.org/nasa/{1}'.format(protocol, efname),
                 body='',
                 status=200,
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'தமிழ் - baz ∆.txt',
                    '--metadata', 'foo:∆']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    with open('internetarchive.log', 'r') as fh:
        assert ('uploaded தமிழ் - baz ∆.txt to {0}//s3.us.archive.org/nasa/'
                '%E0%AE%A4%E0%AE%AE%E0%AE%BF%E0%AE%B4%E0%AF%8D%20-%20'
                'baz%20%E2%88%86.txt'.format(protocol)) in fh.read()


def test_ia_upload_remote_name(tmpdir):
    tmpdir.chdir()
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT, '{0}//s3.us.archive.org/nasa/hi.txt'.format(protocol),
                 body='',
                 status=200,
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'test.txt', '--remote-name',
                    'hi.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    with open('internetarchive.log', 'r') as fh:
        assert ('uploaded hi.txt to {0}//s3.us.archive.org/nasa/'
                'hi.txt'.format(protocol)) in fh.read()
