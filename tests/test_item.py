# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from internetarchive.api import get_item
from internetarchive.utils import norm_filepath
from tests.conftest import PROTOCOL, IaRequestsMock, load_file, \
    NASA_METADATA_PATH, load_test_data_file

try:
    import ujson as json
except ImportError:
    import json
import types
import re
import os
from copy import deepcopy

import pytest
import responses
from requests.exceptions import HTTPError, ConnectionError

from internetarchive import get_session
import internetarchive.files

S3_URL = r'{0}//s3.us.archive.org/'.format(PROTOCOL)
DOWNLOAD_URL_RE = re.compile(r'{0}//archive.org/download/.*'.format(PROTOCOL))
S3_URL_RE = re.compile(r'.*s3.us.archive.org/.*')

EXPECTED_S3_HEADERS = {
    'content-length': '7557',
    'x-archive-queue-derive': '1',
    'x-archive-meta00-scanner': 'uri(Internet%20Archive%20Python%20library',
    'x-archive-size-hint': '7557',
    'x-archive-auto-make-bucket': '1',
    'authorization': 'LOW a:b',
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate',
    'connection': 'close',
}


def test_get_item(nasa_metadata, nasa_item, session):
    assert nasa_item.item_metadata == nasa_metadata
    assert nasa_item.identifier == 'nasa'
    assert nasa_item.exists is True
    assert isinstance(nasa_item.metadata, dict)
    assert isinstance(nasa_item.files, list)
    assert isinstance(nasa_item.reviews, list)
    assert nasa_item.created == 1427273784
    assert nasa_item.d1 == 'ia902606.us.archive.org'
    assert nasa_item.d2 == 'ia802606.us.archive.org'
    assert nasa_item.dir == '/7/items/nasa'
    assert nasa_item.files_count == 6
    assert nasa_item.item_size == 114030
    assert nasa_item.server == 'ia902606.us.archive.org'
    assert nasa_item.uniq == 2131998567
    assert nasa_item.updated == 1427273788
    assert nasa_item.tasks is None
    assert len(nasa_item.collection) == 1


def test_get_file(nasa_item):
    file = nasa_item.get_file('nasa_meta.xml')
    assert type(file) == internetarchive.files.File
    assert file.name == 'nasa_meta.xml'


def test_get_files(nasa_item):
    files = nasa_item.get_files()
    assert isinstance(files, types.GeneratorType)

    expected_files = set(['NASAarchiveLogo.jpg',
                          'globe_west_540.jpg',
                          'nasa_reviews.xml',
                          'nasa_meta.xml',
                          'nasa_archive.torrent',
                          'nasa_files.xml', ])
    files = set(x.name for x in files)
    assert files == expected_files


def test_get_files_by_name(nasa_item):
    files = nasa_item.get_files('globe_west_540.jpg')
    assert set(f.name for f in files) == set(['globe_west_540.jpg'])

    files = nasa_item.get_files(['globe_west_540.jpg', 'nasa_meta.xml'])
    assert set(f.name
               for f in files) == set(['globe_west_540.jpg', 'nasa_meta.xml'])


def test_get_files_by_formats(nasa_item):
    files = set(f.name for f in nasa_item.get_files(formats='Archive BitTorrent'))
    expected_files = set(['nasa_archive.torrent'])
    assert files == expected_files

    files = set(
        f.name for f in nasa_item.get_files(formats=['Archive BitTorrent', 'JPEG']))
    expected_files = set(['nasa_archive.torrent', 'globe_west_540.jpg', ])
    assert files == expected_files


def test_get_files_by_glob(nasa_item):
    files = set(f.name for f in nasa_item.get_files(glob_pattern='*jpg|*torrent'))
    expected_files = set(['NASAarchiveLogo.jpg',
                          'globe_west_540.jpg',
                          'nasa_archive.torrent', ])
    assert files == expected_files

    files = set(f.name
                for f in nasa_item.get_files(glob_pattern=['*jpg', '*torrent']))
    expected_files = set(['NASAarchiveLogo.jpg',
                          'globe_west_540.jpg',
                          'nasa_archive.torrent', ])
    assert files == expected_files


def test_get_files_with_multiple_filters(nasa_item):
    files = set(f.name for f in nasa_item.get_files(formats='JPEG',
                                                    glob_pattern='*xml'))
    expected_files = set(['globe_west_540.jpg',
                          'nasa_reviews.xml',
                          'nasa_meta.xml',
                          'nasa_files.xml', ])
    assert files == expected_files


def test_get_files_no_matches(nasa_item):
    assert list(nasa_item.get_files(formats='none')) == []


def test_download(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content')
        nasa_item.download(files='nasa_meta.xml')
        assert len(tmpdir.listdir()) == 1
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='new test content')
        nasa_item.download(files='nasa_meta.xml')
        with open('nasa/nasa_meta.xml', 'r') as fh:
            assert fh.read() == 'new test content'


def test_download_io_error(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content')
        nasa_item.download(files='nasa_meta.xml')
        rsps.reset()
        with pytest.raises(ConnectionError):
            nasa_item.download(files='nasa_meta.xml')


def test_download_ignore_errors(tmpdir, nasa_item):
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content')
        nasa_item.download(files='nasa_meta.xml')
        nasa_item.download(files='nasa_meta.xml', ignore_errors=True)


def test_download_ignore_existing(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content')
        nasa_item.download(files='nasa_meta.xml', ignore_existing=True)

        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='new test content')
        nasa_item.download(files='nasa_meta.xml', ignore_existing=True)
        with open('nasa/nasa_meta.xml', 'r') as fh:
            assert fh.read() == 'test content'


def test_download_clobber(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content')
        nasa_item.download(files='nasa_meta.xml')

        rsps.reset()
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='new test content')
        nasa_item.download(files='nasa_meta.xml')
        load_file('nasa/nasa_meta.xml') == 'new test content'


def test_download_checksum(tmpdir, caplog):
    tmpdir.chdir()

    # test overwrite based on checksum.
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content')
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='overwrite based on md5')

        nasa_item = get_item('nasa')
        nasa_item.download(files='nasa_meta.xml')
        nasa_item.download(files='nasa_meta.xml', checksum=True)

        assert load_file('nasa/nasa_meta.xml') == 'overwrite based on md5'

        # test no overwrite based on checksum.
        rsps.reset()
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body=load_test_data_file('nasa_meta.xml'))
        nasa_item.download(files='nasa_meta.xml', checksum=True)
        nasa_item.download(files='nasa_meta.xml', checksum=True)

        assert 'skipping nasa' in caplog.text
        assert 'nasa_meta.xml, file already exists based on checksum.' in caplog.text


def test_download_destdir(tmpdir, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='new destdir')
        dest = os.path.join(str(tmpdir), 'new destdir')
        nasa_item.download(files='nasa_meta.xml', destdir=dest)
        assert 'nasa' in os.listdir(dest)
        with open(os.path.join(dest, 'nasa/nasa_meta.xml'), 'r') as fh:
            assert fh.read() == 'new destdir'


def test_download_no_directory(tmpdir, nasa_item):
    url_re = re.compile(r'{0}//archive.org/download/.*'.format(PROTOCOL))
    tmpdir.chdir()
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, url_re, body='no dest dir')
        nasa_item.download(files='nasa_meta.xml', no_directory=True)
        with open(os.path.join(str(tmpdir), 'nasa_meta.xml'), 'r') as fh:
            assert fh.read() == 'no dest dir'


def test_download_dry_run(tmpdir, capsys, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 adding_headers={'content-length': '100'})
        nasa_item.download(formats='Metadata', dry_run=True)

    expected = set(['nasa_reviews.xml', 'nasa_meta.xml', 'nasa_files.xml'])
    out, err = capsys.readouterr()

    assert set([x.split('/')[-1] for x in out.split('\n') if x]) == expected


def test_download_verbose(tmpdir, capsys, nasa_item):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 adding_headers={'content-length': '100'})
        nasa_item.download(files='nasa_meta.xml', verbose=True)
        out, err = capsys.readouterr()
        print(repr(out))
        assert 'downloaded nasa/nasa_meta.xml to' in out
        assert 'nasa_meta.xml' in out


def test_download_dark_item(tmpdir, capsys, nasa_metadata, session):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        nasa_metadata['metadata']['identifier'] = 'dark-item'
        nasa_metadata['is_dark'] = True
        _item_metadata = json.dumps(nasa_metadata)
        rsps.add(responses.GET, '{0}//archive.org/metadata/dark-item'.format(PROTOCOL),
                 body=_item_metadata,
                 content_type='application/json')
        _item = session.get_item('dark-item')
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 status=403,
                 adding_headers={'content-length': '100'})
        _item.download(files='nasa_meta.xml', verbose=True)
        out, err = capsys.readouterr()
        assert 'skipping dark-item, item is dark' in out


def test_upload(nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=EXPECTED_S3_HEADERS)
        _responses = nasa_item.upload(NASA_METADATA_PATH,
                                      access_key='a',
                                      secret_key='b')
        for resp in _responses:
            request = resp.request
            headers = dict((k.lower(), str(v)) for k, v in request.headers.items())
            scanner_header = '%20'.join(
                resp.headers['x-archive-meta00-scanner'].split('%20')[:4])
            headers['x-archive-meta00-scanner'] = scanner_header
            assert 'user-agent' in headers
            del headers['user-agent']
            assert headers == EXPECTED_S3_HEADERS
            assert request.url == '{0}//s3.us.archive.org/nasa/nasa.json'.format(PROTOCOL)


def test_upload_secure_session():
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        c = {'s3': {'access': 'foo', 'secret': 'bar'}, 'general': {'secure': True}}
        s = get_session(config=c)
        rsps.add_metadata_mock('nasa')
        item = s.get_item('nasa')
        with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.PUT, S3_URL_RE)
            r = item.upload(NASA_METADATA_PATH)
            assert r[0].url == 'https://s3.us.archive.org/nasa/nasa.json'


def test_upload_metadata(nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        del _expected_headers['x-archive-meta00-scanner']
        _expected_headers['x-archive-meta00-foo'] = 'bar'
        _expected_headers['x-archive-meta00-subject'] = 'first'
        _expected_headers['x-archive-meta01-subject'] = 'second'
        _expected_headers['x-archive-meta00-baz'] = (
            'uri(%D0%9F%D0%BE%D1%87%D0%B5%D0%BC'
            '%D1%83%20%D0%B1%D1%8B%20%D0%B8%20%'
            'D0%BD%D0%B5%D1%82...)')
        _expected_headers['x-archive-meta00-baz2'] = (
            'uri(%D0%9F%D0%BE%D1%87%D0%B5%D0%BC'
            '%D1%83%20%D0%B1%D1%8B%20%D0%B8%20%'
            'D0%BD%D0%B5%D1%82...)')
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers)
        md = dict(
            foo='bar',
            subject=['first', 'second'],
            baz='Почему бы и нет...',
            baz2=(u'\u041f\u043e\u0447\u0435\u043c\u0443 \u0431\u044b \u0438 '
                  u'\u043d\u0435\u0442...'),
        )
        _responses = nasa_item.upload(NASA_METADATA_PATH,
                                      metadata=md,
                                      access_key='a',
                                      secret_key='b')
        for resp in _responses:
            request = resp.request
            del request.headers['x-archive-meta00-scanner']
            headers = dict((k.lower(), str(v)) for k, v in request.headers.items())
            assert 'user-agent' in headers
            del headers['user-agent']
            assert headers == _expected_headers


def test_upload_503(capsys, nasa_item):
    body = ("<?xml version='1.0' encoding='UTF-8'?>"
            '<Error><Code>SlowDown</Code><Message>Please reduce your request rate.'
            '</Message><Resource>simulated error caused by x-(amz|archive)-simulate-error'
            ', try x-archive-simulate-error:help</Resource><RequestId>d36ec445-8d4a-4a64-'
            'a110-f67af6ee2c2a</RequestId></Error>')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        rsps.add(responses.GET, S3_URL_RE,
                 body='{"over_limit": "1"}')
        rsps.add(responses.PUT, S3_URL_RE,
                 body=body,
                 adding_headers=_expected_headers,
                 status=503)
        try:
            nasa_item.upload(NASA_METADATA_PATH,
                             access_key='a',
                             secret_key='b',
                             retries=1,
                             retries_sleep=.1,
                             verbose=True)
        except Exception as exc:
            assert 'Please reduce your request rate' in str(exc)
            out, err = capsys.readouterr()
            assert 'warning: s3 is overloaded' in err


def test_upload_file_keys(nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE, adding_headers=EXPECTED_S3_HEADERS)
        files = {'new_key.txt': NASA_METADATA_PATH, '222': NASA_METADATA_PATH}
        _responses = nasa_item.upload(files, access_key='a', secret_key='b')
        expected_urls = [
            '{0}//s3.us.archive.org/nasa/new_key.txt'.format(PROTOCOL),
            '{0}//s3.us.archive.org/nasa/222'.format(PROTOCOL)
        ]
        for resp in _responses:
            assert resp.request.url in expected_urls


def test_upload_dir(tmpdir, nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=EXPECTED_S3_HEADERS)

        tmpdir.mkdir('dir_test')
        with open(os.path.join(str(tmpdir), 'dir_test', 'foo.txt'), 'w') as fh:
            fh.write('hi')
        with open(os.path.join(str(tmpdir), 'dir_test', 'foo2.txt'), 'w') as fh:
            fh.write('hi 2')

        # Test no-slash upload, dir is not in key name.
        _responses = nasa_item.upload(os.path.join(str(tmpdir), 'dir_test') + '/',
                                      access_key='a',
                                      secret_key='b')
        expected_eps = [
            '{0}nasa/foo.txt'.format(S3_URL),
            '{0}nasa/foo2.txt'.format(S3_URL),
        ]
        for resp in _responses:
            assert resp.request.url in expected_eps

        # Test slash upload, dir is in key name.
        _responses = nasa_item.upload(os.path.join(str(tmpdir), 'dir_test'),
                                      access_key='a',
                                      secret_key='b')
        tmp_path = norm_filepath(str(tmpdir))
        expected_eps = [
            '{0}nasa{1}/dir_test/{2}'.format(S3_URL, tmp_path, 'foo.txt'),
            '{0}nasa{1}/dir_test/{2}'.format(S3_URL, tmp_path, 'foo2.txt'),
        ]
        for resp in _responses:
            assert resp.request.url in expected_eps


def test_upload_queue_derive(nasa_item):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        _expected_headers['x-archive-queue-derive'] = '1'
        del _expected_headers['x-archive-meta00-scanner']
        rsps.add(responses.PUT, S3_URL_RE, adding_headers=_expected_headers)
        _responses = nasa_item.upload(NASA_METADATA_PATH, access_key='a', secret_key='b')
        for resp in _responses:
            headers = dict((k.lower(), str(v)) for k, v in resp.request.headers.items())
            del headers['x-archive-meta00-scanner']
            assert 'user-agent' in headers
            del headers['user-agent']
            assert headers == _expected_headers


def test_upload_delete(tmpdir, nasa_item):
    body = ("<?xml version='1.0' encoding='UTF-8'?>"
            '<Error><Code>BadDigest</Code><Message>The Content-MD5 you specified did not '
            'match what we received.</Message><Resource>content-md5 submitted with PUT: '
            'foo != recieved data md5: 70871f9fce8dd23853d6e42417356b05also not equal to '
            'base64 version: cIcfn86N0jhT1uQkFzVrBQ==</Resource><RequestId>ec03fe7c-e123-'
            '4133-a207-3141d4d74096</RequestId></Error>')

    _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
    del _expected_headers['x-archive-meta00-scanner']
    tmpdir.chdir()
    test_file = os.path.join(str(tmpdir), 'test.txt')
    with open(test_file, 'w') as fh:
        fh.write('test delete')

    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        # Non-matching md5, should not delete.
        rsps.add(responses.PUT, S3_URL_RE,
                 body=body,
                 adding_headers=_expected_headers,
                 status=400)
        with pytest.raises(HTTPError):
            nasa_item.upload(test_file,
                             access_key='a',
                             secret_key='b',
                             delete=True,
                             queue_derive=True)

        assert len(tmpdir.listdir()) == 1

    _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
    test_file = os.path.join(str(tmpdir), 'test.txt')
    with open(test_file, 'w') as fh:
        fh.write('test delete')

    # Matching md5, should delete.
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers)
        resp = nasa_item.upload(test_file,
                                access_key='a',
                                secret_key='b',
                                delete=True,
                                queue_derive=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            del headers['content-type']
            assert headers == _expected_headers
            assert len(tmpdir.listdir()) == 0


def test_upload_checksum(tmpdir, nasa_item):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        nasa_item = get_item('nasa')

        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        del _expected_headers['x-archive-meta00-scanner']
        _expected_headers['content-md5'] = '6f1834f5c70c0eabf93dea675ccf90c4'

        test_file = os.path.join(str(tmpdir), 'checksum_test.txt')
        with open(test_file, 'wb') as fh:
            fh.write(b'test delete')

        # No skip.
        rsps.add(responses.PUT, S3_URL_RE, adding_headers=_expected_headers)
        resp = nasa_item.upload(test_file,
                                access_key='a',
                                secret_key='b',
                                checksum=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            del headers['content-type']
            assert headers == _expected_headers
            assert r.status_code == 200

        # Skip.
        nasa_item.item_metadata['files'].append(
            dict(name='checksum_test.txt',
                 md5='33213e7683c1e6d15b2a658f3c567717'))
        resp = nasa_item.upload(test_file,
                                access_key='a',
                                secret_key='b',
                                checksum=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            assert r.status_code is None


def test_modify_metadata(nasa_item, nasa_metadata):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST, '{0}//archive.org/metadata/nasa'.format(PROTOCOL))

        # Test simple add.
        md = {'foo': 'bar'}
        p = nasa_item.modify_metadata(md, debug=True)
        _patch = json.dumps([
            {"add": "/foo", "value": "bar"},
        ])
        expected_data = {
            'priority': -5,
            '-target': 'metadata',
            '-patch': _patch,
        }
        assert set(p.data.keys()) == set(expected_data.keys())
        assert p.data['priority'] == expected_data['priority']
        assert p.data['-target'] == expected_data['-target']
        assert all(v in p.data['-patch'] for v in ['/foo', 'bar'])
        # Test no changes.
        md = {'title': 'NASA Images'}
        p = nasa_item.modify_metadata(md, debug=True)
        expected_data = {'priority': -5, '-target': 'metadata', '-patch': '[]'}
        assert p.data == expected_data

        md = {'title': 'REMOVE_TAG'}
        p = nasa_item.modify_metadata(md, debug=True)
        expected_data = {
            'priority': -5,
            '-target': 'metadata',
            '-patch': json.dumps([{"remove": "/title"}])
        }
        assert set(p.data.keys()) == set(expected_data.keys())
        assert p.data['priority'] == expected_data['priority']
        assert p.data['-target'] == expected_data['-target']
        assert '/title' in str(p.data['-patch'])
        assert 'remove' in str(p.data['-patch'])

        # Test add array.
        md = {'subject': ['one', 'two', 'last']}
        p = nasa_item.modify_metadata(md, debug=True, priority=-1)
        expected_data = {
            'priority': -1,
            '-target': 'metadata',
            '-patch': json.dumps([{"add": "/subject", "value": ["one", "two", "last"]}])
        }
        assert set(p.data.keys()) == set(expected_data.keys())
        assert p.data['priority'] == expected_data['priority']
        assert p.data['-target'] == expected_data['-target']
        assert '["one", "two", "last"]' in str(p.data['-patch'])

        # Test indexed mod.
        nasa_item.item_metadata['metadata']['subject'] = ['first', 'middle', 'last']
        md = {'subject[2]': 'new first'}
        p = nasa_item.modify_metadata(md, debug=True)
        expected_data = {
            'priority': -5,
            '-target': 'metadata',
            '-patch': json.dumps([{"value": "new first", "replace": "/subject/2"}])
        }

        # Avoid comparing the json strings, because they are not in a canonical form
        assert set(p.data.keys()) == set(expected_data.keys())
        assert all(p.data[k] == expected_data[k] for k in ['priority', '-target'])
        assert '/subject/2' in p.data['-patch']

        # Test priority.
        md = {'title': 'NASA Images'}
        p = nasa_item.modify_metadata(md, priority=3, debug=True)
        expected_data = {'priority': 3, '-target': 'metadata', '-patch': '[]'}
        assert p.data == expected_data

        # Test auth.
        md = {'title': 'NASA Images'}
        p = nasa_item.modify_metadata(md,
                                      access_key='a',
                                      secret_key='b',
                                      debug=True)
        assert 'access=a' in p.body
        assert 'secret=b' in p.body

        # Test change.
        md = {'title': 'new title'}
        nasa_metadata['metadata']['title'] = 'new title'
        _item_metadata = json.dumps(nasa_metadata)
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(PROTOCOL),
                 body=_item_metadata)
        nasa_item.modify_metadata(md,
                                  access_key='a',
                                  secret_key='b')
        # Test that item re-initializes
        assert nasa_item.metadata['title'] == 'new title'
