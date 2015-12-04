import os
import sys
import json

import requests
import responses

from internetarchive.cli import ia


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')

with open(TEST_JSON_FILE, 'r') as fh:
    ITEM_METADATA = fh.read().strip().decode('utf-8')
with open(os.path.join(ROOT_DIR, 'tests/data/s3_status_check.json'), 'r') as fh:
    STATUS_CHECK_RESPONSE = fh.read().strip().decode('utf-8')



def test_ia_upload(tmpdir):
    tmpdir.chdir()
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT, 'http://s3.us.archive.org/nasa/test.txt',
                 body='',
                 status=200,
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'test.txt']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    with open('internetarchive.log', 'r') as fh:
        assert 'uploaded test.txt to http://s3.us.archive.org/nasa/test.txt' in fh.read()


def test_ia_upload_status_check(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://s3.us.archive.org',
                 body=STATUS_CHECK_RESPONSE,
                 status=200,
                 content_type='application/json')

        sys.argv = ['ia', 'upload', 'nasa', '--status-check']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

        out, err = capsys.readouterr()
        assert 'success: nasa is accepting requests.' in out

        j = json.loads(STATUS_CHECK_RESPONSE)
        j['over_limit'] = 1
        rsps.add(responses.GET, 'http://s3.us.archive.org',
                 body=json.dumps(j),
                 status=200,
                 content_type='application/json')

        sys.argv = ['ia', 'upload', 'nasa', '--status-check']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

        out, err = capsys.readouterr()
        assert ('warning: nasa is over limit, and not accepting requests. '
                'Expect 503 SlowDown errors.') in err


def test_ia_upload_debug(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        sys.argv = ['ia', 'upload', '--debug', 'nasa', 'test.txt']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    assert out == ('nasa:\n'
                   'Endpoint:\n'
                   ' http://s3.us.archive.org/nasa/test.txt\n\n'
                   'HTTP Headers:\n'
                   ' x-archive-size-hint:3\n'
                   ' Content-MD5:acbd18db4cc2f85cedef654fccc4a4d8\n')


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
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT, 'http://s3.us.archive.org/nasa/test_ia_upload.py',
                 body=s3_error,
                 status=403,
                 content_type='text/plain')
        sys.argv = ['ia', 'upload', 'nasa', __file__]
        try:
            r = ia.main()
        except SystemExit as exc:
            assert exc.code == 1

    out, err = capsys.readouterr()
    assert 'error uploading test_ia_upload.py to nasa, 403' in err


def test_ia_upload_invalid_cmd(capsys):
    sys.argv = ['ia', 'upload', 'nasa', 'nofile.txt']
    try:
        r = ia.main()
    except SystemExit as exc:
        assert exc.code == 1

    out, err = capsys.readouterr()
    assert '<file> should be a readable file or directory.' in err


def test_ia_upload_size_hint(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        sys.argv = ['ia', 'upload', '--debug', 'nasa', '--size-hint', '30', 'test.txt']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    assert out == ('nasa:\n'
                   'Endpoint:\n'
                   ' http://s3.us.archive.org/nasa/test.txt\n\n'
                   'HTTP Headers:\n'
                   ' x-archive-size-hint:30\n'
                   ' Content-MD5:acbd18db4cc2f85cedef654fccc4a4d8\n')


def test_ia_upload_remote_name(tmpdir):
    tmpdir.chdir()
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200,
                 content_type='application/json')
        rsps.add(responses.PUT, 'http://s3.us.archive.org/nasa/hi.txt',
                 body='',
                 status=200,
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'test.txt', '--remote-name', 'hi.txt']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    with open('internetarchive.log', 'r') as fh:
        assert 'uploaded hi.txt to http://s3.us.archive.org/nasa/hi.txt' in fh.read()
