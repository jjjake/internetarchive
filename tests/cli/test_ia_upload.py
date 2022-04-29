import os
import sys
from contextlib import contextmanager
from io import StringIO

import responses

from internetarchive.utils import json
from tests.conftest import IaRequestsMock, ia_call, load_test_data_file

PROTOCOL = 'https:'
STATUS_CHECK_RESPONSE = load_test_data_file('s3_status_check.json')


def test_ia_upload(tmpdir_ch, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', 'nasa', 'test.txt'])

    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text


def test_ia_upload_invalid_identifier(capsys, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    ia_call(['ia', '--log', 'upload', 'føø', 'test.txt'],
            expected_exit_code=1)

    out, err = capsys.readouterr()
    assert ('<identifier> should be between 3 and 80 characters in length, and '
            'can only contain alphanumeric characters, periods ".", '
            'underscores "_", or dashes "-". However, <identifier> cannot begin '
            'with periods, underscores, or dashes.') in err


def test_ia_upload_status_check(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, f'{PROTOCOL}//s3.us.archive.org',
                 body=STATUS_CHECK_RESPONSE,
                 content_type='application/json')

        ia_call(['ia', 'upload', 'nasa', '--status-check'])
        out, err = capsys.readouterr()
        assert 'success: nasa is accepting requests.' in err

        j = json.loads(STATUS_CHECK_RESPONSE)
        j['over_limit'] = 1
        rsps.reset()
        rsps.add(responses.GET, f'{PROTOCOL}//s3.us.archive.org',
                 body=json.dumps(j),
                 content_type='application/json')

        ia_call(['ia', 'upload', 'nasa', '--status-check'], expected_exit_code=1)
        out, err = capsys.readouterr()
        assert ('warning: nasa is over limit, and not accepting requests. '
                'Expect 503 SlowDown errors.') in err


def test_ia_upload_debug(capsys, tmpdir_ch, nasa_mocker):
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    ia_call(['ia', 'upload', '--debug', 'nasa', 'test.txt'])
    out, err = capsys.readouterr()
    assert 'User-Agent' in err
    assert 's3.us.archive.org/nasa/test.txt' in err
    assert 'Accept:*/*' in err
    assert 'Authorization:LOW ' in err
    assert 'Connection:close' in err
    assert 'Content-Length:3' in err
    assert 'Accept-Encoding:gzip, deflate' in err


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
                 f'{PROTOCOL}//s3.us.archive.org/nasa/test_ia_upload.py',
                 body=s3_error,
                 status=403,
                 content_type='text/plain')
        ia_call(['ia', 'upload', 'nasa', __file__], expected_exit_code=1)

    out, err = capsys.readouterr()
    assert 'error uploading test_ia_upload.py' in err


def test_ia_upload_invalid_cmd(capsys):
    ia_call(['ia', 'upload', 'nasa', 'nofile.txt'], expected_exit_code=1)
    out, err = capsys.readouterr()
    assert '<file> should be a readable file or directory.' in err


def test_ia_upload_size_hint(capsys, tmpdir_ch, nasa_mocker):
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    ia_call(['ia', 'upload', '--debug', 'nasa', '--size-hint', '30', 'test.txt'])
    out, err = capsys.readouterr()
    assert 'User-Agent' in err
    assert 's3.us.archive.org/nasa/test.txt' in err
    assert 'x-archive-size-hint:30' in err
    assert 'Accept:*/*' in err
    assert 'Authorization:LOW ' in err
    assert 'Connection:close' in err
    assert 'Content-Length:3' in err
    assert 'Accept-Encoding:gzip, deflate' in err


def test_ia_upload_unicode(tmpdir_ch, caplog):
    with open('தமிழ் - baz ∆.txt', 'w') as fh:
        fh.write('unicode foo')

    efname = '%E0%AE%A4%E0%AE%AE%E0%AE%BF%E0%AE%B4%E0%AF%8D%20-%20baz%20%E2%88%86.txt'
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT,
                 f'{PROTOCOL}//s3.us.archive.org/nasa/{efname}',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', 'nasa', 'தமிழ் - baz ∆.txt',
                 '--metadata', 'foo:∆'])

    assert (f'uploaded தமிழ் - baz ∆.txt to {PROTOCOL}//s3.us.archive.org/nasa/'
            '%E0%AE%A4%E0%AE%AE%E0%AE%BF%E0%AE%B4%E0%AF%8D%20-%20'
            'baz%20%E2%88%86.txt') in caplog.text


def test_ia_upload_remote_name(tmpdir_ch, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/hi.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', 'nasa', 'test.txt', '--remote-name',
                 'hi.txt'])

    assert f'uploaded hi.txt to {PROTOCOL}//s3.us.archive.org/nasa/hi.txt' in caplog.text


def test_ia_upload_stdin(tmpdir_ch, caplog):
    @contextmanager
    def replace_stdin(f):
        original_stdin = sys.stdin
        sys.stdin = f
        try:
            yield
        finally:
            sys.stdin = original_stdin

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/hi.txt',
                 body='',
                 content_type='text/plain')
        with replace_stdin(StringIO('foo')):
            ia_call(['ia', '--log', 'upload', 'nasa', '-', '--remote-name', 'hi.txt'])

    assert f'uploaded hi.txt to {PROTOCOL}//s3.us.archive.org/nasa/hi.txt' in caplog.text


def test_ia_upload_inexistent_file(tmpdir_ch, capsys, caplog):
    ia_call(['ia', 'upload', 'foo', 'test.txt'], expected_exit_code=1)
    out, err = capsys.readouterr()
    assert '<file> should be a readable file or directory.' in err


def test_ia_upload_spreadsheet(tmpdir_ch, caplog):
    with open('foo.txt', 'w') as fh:
        fh.write('foo')
    with open('test.txt', 'w') as fh:
        fh.write('bar')
    with open('test.csv', 'w') as fh:
        fh.write('identifier,file,REMOTE_NAME\n')
        fh.write('nasa,foo.txt,\n')
        fh.write(',test.txt,bar.txt\n')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/foo.txt',
                 body='',
                 content_type='text/plain')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/bar.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', 'upload', '--spreadsheet', 'test.csv'])

    assert f'uploaded foo.txt to {PROTOCOL}//s3.us.archive.org/nasa/foo.txt' in caplog.text
    assert f'uploaded bar.txt to {PROTOCOL}//s3.us.archive.org/nasa/bar.txt' in caplog.text


def test_ia_upload_spreadsheet_item_column(tmpdir_ch, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')
    with open('test.csv', 'w') as fh:
        fh.write('item,file\n')
        fh.write('nasa,test.txt\n')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', 'upload', '--spreadsheet', 'test.csv'])

    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text


def test_ia_upload_spreadsheet_item_and_identifier_column(tmpdir_ch, caplog):
    # item is preferred, and both are discarded
    with open('test.txt', 'w') as fh:
        fh.write('foo')
    with open('test.csv', 'w') as fh:
        fh.write('item,identifier,file\n')
        fh.write('nasa,uhoh,test.txt\n')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')

        ia_call(['ia', 'upload', '--spreadsheet', 'test.csv'])

        # Verify that the item and identifier columns are not in the PUT request headers
        putCalls = [c for c in rsps.calls if c.request.method == 'PUT']
        assert len(putCalls) == 1
        assert 'x-archive-meta00-identifier' not in putCalls[0].request.headers
        assert 'x-archive-meta00-item' not in putCalls[0].request.headers

    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text


def test_ia_upload_spreadsheet_missing_identifier(tmpdir_ch, capsys, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')
    with open('test.csv', 'w') as fh:
        fh.write('file\n')
        fh.write('test.txt\n')

    ia_call(['ia', 'upload', '--spreadsheet', 'test.csv'], expected_exit_code=1)

    assert 'error: no identifier column on spreadsheet.' in capsys.readouterr().err


def test_ia_upload_spreadsheet_empty_identifier(tmpdir_ch, capsys, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')
    with open('test.csv', 'w') as fh:
        fh.write('identifier,file\n')
        fh.write(',test.txt\n')

    ia_call(['ia', 'upload', '--spreadsheet', 'test.csv'], expected_exit_code=1)

    assert 'error: no identifier column on spreadsheet.' in capsys.readouterr().err


def test_ia_upload_spreadsheet_bom(tmpdir_ch, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')
    with open('test.csv', 'wb') as fh:
        fh.write(b'\xef\xbb\xbf')
        fh.write(b'identifier,file\n')
        fh.write(b'nasa,test.txt\n')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', 'upload', '--spreadsheet', 'test.csv'])

    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text


def test_ia_upload_checksum(tmpdir_ch, caplog):
    with open('test.txt', 'w') as fh:
        fh.write('foo')

    # First upload, file not in metadata yet
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', 'nasa', 'test.txt', '--checksum'])
    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text

    caplog.clear()

    # Second upload with file in metadata
    def insert_test_txt(body):
        body = json.loads(body)
        body['files'].append({'name': 'test.txt', 'md5': 'acbd18db4cc2f85cedef654fccc4a4d8'})
        return json.dumps(body)

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', transform_body=insert_test_txt)
        ia_call(['ia', '--log', 'upload', 'nasa', 'test.txt', '--checksum'], expected_exit_code=1)

    assert f'test.txt already exists: {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text

    caplog.clear()

    # Second upload with spreadsheet
    with open('test.csv', 'w') as fh:
        fh.write('identifier,file\n')
        fh.write('nasa,test.txt\n')

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', transform_body=insert_test_txt)
        ia_call(['ia', '--log', 'upload', '--spreadsheet', 'test.csv', '--checksum'],
                expected_exit_code=1)

    assert f'test.txt already exists: {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text


def test_ia_upload_keep_directories(tmpdir_ch, caplog):
    os.mkdir('foo')
    with open('foo/test.txt', 'w') as fh:
        fh.write('foo')
    with open('test.csv', 'w') as fh:
        fh.write('identifier,file\n')
        fh.write('nasa,foo/test.txt\n')

    # Default behaviour
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', 'nasa', 'foo/test.txt'])
    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text
    caplog.clear()

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', '--spreadsheet', 'test.csv'])
    assert f'uploaded test.txt to {PROTOCOL}//s3.us.archive.org/nasa/test.txt' in caplog.text
    caplog.clear()

    # With the option
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/foo/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', 'nasa', 'foo/test.txt', '--keep-directories'])
    assert f'uploaded foo/test.txt to {PROTOCOL}//s3.us.archive.org/nasa/foo/test.txt' in caplog.text
    caplog.clear()

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.PUT, f'{PROTOCOL}//s3.us.archive.org/nasa/foo/test.txt',
                 body='',
                 content_type='text/plain')
        ia_call(['ia', '--log', 'upload', '--spreadsheet', 'test.csv', '--keep-directories'])
    assert f'uploaded foo/test.txt to {PROTOCOL}//s3.us.archive.org/nasa/foo/test.txt' in caplog.text
