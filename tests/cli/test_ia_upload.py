# -*- coding: utf-8 -*-
import sys

from tests.conftest import IaRequestsMock, load_test_data_file

import json

import responses

from internetarchive.cli import ia


PROTOCOL = 'https:'
STATUS_CHECK_RESPONSE = load_test_data_file('s3_status_check.json')


def test_ia_upload(tmpdir, caplog):
    tmpdir.chdir()
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, '{0}//s3.us.archive.org/nasa/test.txt'.format(PROTOCOL),
                 body='',
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'test.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    assert ('uploaded test.txt to {0}//s3.us.archive.org/nasa/'
            'test.txt'.format(PROTOCOL)) in caplog.text()


def test_ia_upload_status_check(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//s3.us.archive.org'.format(PROTOCOL),
                 body=STATUS_CHECK_RESPONSE,
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
        rsps.add(responses.GET, '{0}//s3.us.archive.org'.format(PROTOCOL),
                 body=json.dumps(j),
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
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
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
        ' {0}//s3.us.archive.org/nasa/test.txt'.format(PROTOCOL),
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

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT,
                 '{0}//s3.us.archive.org/nasa/test_ia_upload.py'.format(PROTOCOL),
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
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        sys.argv = ['ia', 'upload', '--debug', 'nasa', '--size-hint', '30', 'test.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    assert set(out.split('\n')) == set(['', ' x-archive-size-hint:30',
                                        'Endpoint:', 'HTTP Headers:', 'nasa:',
                                        (' {0}//s3.us.archive.org/nasa/'
                                         'test.txt'.format(PROTOCOL))])


def test_ia_upload_unicode(tmpdir, caplog):
    tmpdir.chdir()
    with open('தமிழ் - baz ∆.txt', 'w') as fh:
        fh.write('unicode foo')
    fname = u'தமிழ் - foo; baz ∆.txt'
    efname = '%E0%AE%A4%E0%AE%AE%E0%AE%BF%E0%AE%B4%E0%AF%8D%20-%20baz%20%E2%88%86.txt'
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT,
                 '{0}//s3.us.archive.org/nasa/{1}'.format(PROTOCOL, efname),
                 body='',
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'தமிழ் - baz ∆.txt',
                    '--metadata', 'foo:∆']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    assert (u'uploaded தமிழ் - baz ∆.txt to {0}//s3.us.archive.org/nasa/'
            u'%E0%AE%A4%E0%AE%AE%E0%AE%BF%E0%AE%B4%E0%AF%8D%20-%20'
            u'baz%20%E2%88%86.txt'.format(PROTOCOL)) in caplog.text()


def test_ia_upload_remote_name(tmpdir, caplog):
    tmpdir.chdir()
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, '{0}//s3.us.archive.org/nasa/hi.txt'.format(PROTOCOL),
                 body='',
                 content_type='text/plain')
        sys.argv = ['ia', '--log', 'upload', 'nasa', 'test.txt', '--remote-name',
                    'hi.txt']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    assert ('uploaded hi.txt to {0}//s3.us.archive.org/nasa/'
            'hi.txt'.format(PROTOCOL)) in caplog.text()
