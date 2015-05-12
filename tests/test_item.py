import json
import types
import re
import os
from copy import deepcopy
import shutil

import pytest
import responses
from requests.exceptions import HTTPError

from internetarchive import get_session
import internetarchive.files


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')

DOWNLOAD_URL_RE = re.compile(r'http://archive.org/download/.*')
S3_URL_RE = re.compile(r'.*s3.us.archive.org/.*')
EXPECTED_S3_HEADERS = {
    'content-length': '7557',
    'x-archive-queue-derive': '1',
    'x-archive-meta00-scanner': 'uri(Internet%20Archive%20Python%20library',
    'x-archive-size-hint': '7557',
    'content-md5': '6f1834f5c70c0eabf93dea675ccf90c4',
    'x-archive-auto-make-bucket': '1',
    'authorization': 'LOW test_access:test_secret',
}



# Helper functions _______________________________________________________________________
def get_test_item_md():
    with open(TEST_JSON_FILE, 'r') as fh:
        item_metadata = fh.read().strip().decode('utf-8')
    return item_metadata


@responses.activate
def get_session_and_item(item_metadata=None):
    if not item_metadata:
        item_metadata = get_test_item_md()
    s = get_session()
    responses.add(responses.GET, 'http://archive.org/metadata/nasa',
                  body=item_metadata,
                  status=200,
                  content_type='application/json')
    item = s.get_item('nasa')
    return s, item, item_metadata


# get_item() _____________________________________________________________________________
def test_get_item():
    s, item, item_metadata = get_session_and_item()

    assert item.item_metadata == json.loads(item_metadata)
    assert item.identifier == 'nasa'
    assert item.exists == True
    assert item.session == s
    assert isinstance(item.metadata, dict)
    assert isinstance(item.files, list)
    assert isinstance(item.reviews, list)
    assert item.created == 1427273784
    assert item.d1 == 'ia902606.us.archive.org'
    assert item.d2 == 'ia802606.us.archive.org'
    assert item.dir == '/7/items/nasa'
    assert item.files_count == 6
    assert item.item_size == 114030
    assert item.server == 'ia902606.us.archive.org'
    assert item.uniq == 2131998567
    assert item.updated == 1427273788
    assert item.tasks == None
    assert repr(item) == "Item(identifier=u'nasa', exists=True)"


# get_file() _____________________________________________________________________________
def test_get_file():
    s, item, item_metadata = get_session_and_item()
    _file = item.get_file('nasa_meta.xml')
    assert type(_file) == internetarchive.files.File
    assert _file.name == 'nasa_meta.xml'


def test_get_files():
    s, item, item_metadata = get_session_and_item()

    files = item.get_files()
    assert type(files) == types.GeneratorType

    expected_files = set(['NASAarchiveLogo.jpg',
                          'globe_west_540.jpg',
                          'nasa_reviews.xml',
                          'nasa_meta.xml',
                          'nasa_archive.torrent',
                          'nasa_files.xml', ])
    files = set(x.name for x in files)
    assert files == expected_files


def test_get_files_by_name():
    s, item, item_metadata = get_session_and_item()

    files = item.get_files('globe_west_540.jpg')
    assert set(f.name for f in files) == set(['globe_west_540.jpg'])

    files = item.get_files(['globe_west_540.jpg', 'nasa_meta.xml'])
    assert set(f.name
               for f in files) == set(['globe_west_540.jpg', 'nasa_meta.xml'])


def test_get_files_by_source():
    s, item, item_metadata = get_session_and_item()

    files = set(f.name for f in item.get_files(source='metadata'))
    expected_files = set(['nasa_reviews.xml',
                          'nasa_meta.xml',
                          'nasa_archive.torrent',
                          'nasa_files.xml', ])
    assert files == expected_files

    files = set(f.name
                for f in item.get_files(source=['metadata', 'original']))
    expected_files = set(['nasa_reviews.xml',
                          'nasa_meta.xml',
                          'nasa_archive.torrent',
                          'nasa_files.xml',
                          'globe_west_540.jpg',
                          'NASAarchiveLogo.jpg', ])
    assert files == expected_files


def test_get_files_by_formats():
    s, item, item_metadata = get_session_and_item()

    files = set(f.name for f in item.get_files(formats='Archive BitTorrent'))
    expected_files = set(['nasa_archive.torrent'])
    assert files == expected_files

    files = set(
        f.name for f in item.get_files(formats=['Archive BitTorrent', 'JPEG']))
    expected_files = set(['nasa_archive.torrent', 'globe_west_540.jpg', ])
    assert files == expected_files


def test_get_files_by_glob():
    s, item, item_metadata = get_session_and_item()

    files = set(f.name for f in item.get_files(glob_pattern='*jpg|*torrent'))
    expected_files = set(['NASAarchiveLogo.jpg',
                          'globe_west_540.jpg',
                          'nasa_archive.torrent', ])
    assert files == expected_files

    files = set(f.name
                for f in item.get_files(glob_pattern=['*jpg', '*torrent']))
    expected_files = set(['NASAarchiveLogo.jpg',
                          'globe_west_540.jpg',
                          'nasa_archive.torrent', ])
    assert files == expected_files


def test_get_files_with_multiple_filters():
    s, item, item_metadata = get_session_and_item()

    files = set(f.name for f in item.get_files(formats='JPEG',
                                               glob_pattern='*xml'))
    expected_files = set(['globe_west_540.jpg',
                          'nasa_reviews.xml',
                          'nasa_meta.xml',
                          'nasa_files.xml', ])
    assert files == expected_files


def test_get_files_no_matches():
    s, item, item_metadata = get_session_and_item()

    assert list(item.get_files(formats='none')) == []


# download() _____________________________________________________________________________
def test_download(tmpdir):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content', status=200)
        item.download(files='nasa_meta.xml')
        assert len(tmpdir.listdir()) == 1


def test_download_io_error(tmpdir):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    try:
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, DOWNLOAD_URL_RE, body='test content', status=200)
            item.download(files='nasa_meta.xml')
            item.download(files='nasa_meta.xml')
    except Exception as exc:
        assert isinstance(exc, IOError)


def test_download_no_clobber(tmpdir):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 status=200)
        item.download(files='nasa_meta.xml', no_clobber=True)

        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='new test content',
                 status=200)
        item.download(files='nasa_meta.xml', no_clobber=True)
        with open('nasa/nasa_meta.xml', 'r') as fh:
            assert fh.read() == 'test content'


def test_download_clobber(tmpdir):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 status=200)
        item.download(files='nasa_meta.xml', clobber=True)

        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='new test content',
                 status=200)
        item.download(files='nasa_meta.xml', clobber=True)
        with open('nasa/nasa_meta.xml', 'r') as fh:
            assert fh.read() == 'new test content'


def test_download_checksum(tmpdir):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()

    # test overwrite based on checksum.
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='test content',
                 status=200)
        item.download(files='nasa_meta.xml', clobber=True)

        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='overwrite based on md5',
                 status=200)
        item.download(files='nasa_meta.xml', checksum=True)
        with open('nasa/nasa_meta.xml', 'r') as fh:
            assert fh.read() == 'overwrite based on md5'

    # test no overwrite based on checksum.
    with open(os.path.join(ROOT_DIR, 'tests/data/nasa_meta.xml'), 'r') as fh:
        nasa_meta_xml = fh.read()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body=nasa_meta_xml, status=200)
        item.download(files='nasa_meta.xml', checksum=True)
        r = item.download(files='nasa_meta.xml', checksum=True)
        assert r[0] is None


def test_download_destdir(tmpdir):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE, body='new destdir', status=200)
        dest = os.path.join(str(tmpdir), 'new destdir')
        item.download(files='nasa_meta.xml', destdir=dest)
        assert 'nasa' in os.listdir(dest)
        with open(os.path.join(dest, 'nasa/nasa_meta.xml'), 'r') as fh:
            assert fh.read() == 'new destdir'


def test_download_no_directory(tmpdir):
    s, item, item_metadata = get_session_and_item()
    url_re = re.compile(r'http://archive.org/download/.*')
    tmpdir.chdir()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, url_re, body='no dest dir', status=200)
        item.download(files='nasa_meta.xml', no_directory=True)
        with open(os.path.join(str(tmpdir), 'nasa_meta.xml'), 'r') as fh:
            assert fh.read() == 'no dest dir'


def test_download_dry_run(tmpdir, capsys):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 status=200,
                 adding_headers={'content-length': '100'})
        item.download(source='original', dry_run=True)
        out, err = capsys.readouterr()
        expected_output = ('http://archive.org/download/nasa/NASAarchiveLogo.jpg\n'
                           'http://archive.org/download/nasa/globe_west_540.jpg\n')
        assert expected_output == out


def test_download_verbose(tmpdir, capsys):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 status=200,
                 adding_headers={'content-length': '100'})
        item.download(files='nasa_meta.xml', clobber=True, verbose=True)
        out, err = capsys.readouterr()
        assert 'nasa:' in err


def test_download_dark_item(tmpdir, capsys):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        _item_metadata = json.loads(item_metadata)
        _item_metadata['metadata']['identifier'] = 'dark-item'
        _item_metadata['is_dark'] = True
        _item_metadata = json.dumps(_item_metadata)
        rsps.add(responses.GET, 'http://archive.org/metadata/dark-item',
                      body=_item_metadata,
                      status=200,
                      content_type='application/json')
        _item = s.get_item('dark-item')
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 status=403,
                 adding_headers={'content-length': '100'})
        _item.download(files='nasa_meta.xml', clobber=True, verbose=True)
        out, err = capsys.readouterr()
        assert 'skipping: item is dark.' in err


def test_download_dark_item(tmpdir, capsys):
    s, item, item_metadata = get_session_and_item()
    tmpdir.chdir()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/idontexist',
                      body='{}',
                      status=200,
                      content_type='application/json')
        _item = s.get_item('idontexist')
        rsps.add(responses.GET, DOWNLOAD_URL_RE,
                 body='no dest dir',
                 status=404)
        _item.download(files='nasa_meta.xml', clobber=True, verbose=True)
        out, err = capsys.readouterr()
        assert 'item does not exist.' in err


# upload() _______________________________________________________________________________
def test_upload():
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=EXPECTED_S3_HEADERS,
                 status=200)
        resp = item.upload(TEST_JSON_FILE,
                           access_key='test_access',
                           secret_key='test_secret',
                           debug=True)
        for r in resp:
            p = r.prepare()
            headers = dict((k.lower(), str(v)) for k, v in p.headers.items())
            scanner_header = '%20'.join(
                r.headers['x-archive-meta00-scanner'].split('%20')[:4])
            headers['x-archive-meta00-scanner'] = scanner_header
            assert headers == EXPECTED_S3_HEADERS
            assert p.url == 'http://s3.us.archive.org/nasa/nasa_meta.json'


def test_upload_secure_session():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        s = get_session(config=dict(secure=True))
        rsps.add(responses.GET, 'https://archive.org/metadata/nasa',
                 body=get_test_item_md(),
                 status=200)
        item = s.get_item('nasa')
        with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.PUT, S3_URL_RE, status=200)
            r = item.upload(TEST_JSON_FILE)
            assert r[0].url == 'https://s3.us.archive.org/nasa/nasa_meta.json'


def test_upload_metadata():
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        del _expected_headers['x-archive-meta00-scanner']
        _expected_headers['x-archive-meta00-foo'] = 'bar'
        _expected_headers['x-archive-meta00-subject'] = 'first'
        _expected_headers['x-archive-meta01-subject'] = 'second'
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers,
                 status=200)
        md = dict(foo='bar', subject=['first', 'second'])
        resp = item.upload(TEST_JSON_FILE,
                           metadata=md,
                           access_key='test_access',
                           secret_key='test_secret',
                           debug=True)
        for r in resp:
            p = r.prepare()
            del p.headers['x-archive-meta00-scanner']
            headers = dict((k.lower(), str(v)) for k, v in p.headers.items())
            assert headers == _expected_headers


def test_upload_503(capsys):
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        rsps.add(responses.GET, S3_URL_RE,
                 body='{"over_limit": "1"}',
                 status=200)
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers,
                 status=503)
        try:
            resp = item.upload(TEST_JSON_FILE,
                               access_key='test_access',
                               secret_key='test_secret',
                               retries=1,
                               retries_sleep=.1,
                               verbose=True)
        except Exception as exc:
            assert '503' in str(exc)
            out, err = capsys.readouterr()
            assert 'warning: s3 is overloaded' in err


def test_upload_file_keys():
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=EXPECTED_S3_HEADERS,
                 status=200)
        files = {'new_key.txt': TEST_JSON_FILE, 222: TEST_JSON_FILE}
        resp = item.upload(files,
                           access_key='test_access',
                           secret_key='test_secret',
                           debug=True)
        for r in resp:
            p = r.prepare()
            assert p.url in ['http://s3.us.archive.org/nasa/new_key.txt',
                             'http://s3.us.archive.org/nasa/222']


def test_upload_dir(tmpdir):
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=EXPECTED_S3_HEADERS,
                 status=200)

        tmpdir.mkdir('dir_test')
        with open(os.path.join(str(tmpdir), 'dir_test', 'foo.txt'), 'w') as fh:
            fh.write('hi')
        with open(os.path.join(str(tmpdir), 'dir_test', 'foo2.txt'), 'w') as fh:
            fh.write('hi 2')

        # Test no-slash upload, dir is not in key name.
        resp = item.upload(os.path.join(str(tmpdir), 'dir_test') + '/',
                           access_key='test_access',
                           secret_key='test_secret',
                           debug=True)
        for r in resp:
            p = r.prepare()
            expected_eps = [
                    'http://s3.us.archive.org/nasa/foo.txt',
                    'http://s3.us.archive.org/nasa/foo2.txt',
            ]
            assert p.url in expected_eps

        # Test slash upload, dir is in key name.
        resp = item.upload(os.path.join(str(tmpdir), 'dir_test'),
                           access_key='test_access',
                           secret_key='test_secret',
                           debug=True)
        for r in resp:
            p = r.prepare()
            expected_eps = [
                'http://s3.us.archive.org/nasa{0}/dir_test/{1}'.format(str(tmpdir), 'foo.txt'),
                'http://s3.us.archive.org/nasa{0}/dir_test/{1}'.format(str(tmpdir), 'foo2.txt'),
            ]
            assert p.url in expected_eps
        #shutil.rmtree(os.path.join(str(tmpdir), 'dir_test'))


def test_upload_queue_derive():
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        _expected_headers['x-archive-queue-derive'] = '1'
        del _expected_headers['x-archive-meta00-scanner']
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers,
                 status=200)
        resp = item.upload(TEST_JSON_FILE,
                           access_key='test_access',
                           secret_key='test_secret',
                           queue_derive=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            del headers['content-type']
            assert headers == _expected_headers


def test_upload_delete(tmpdir):
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        del _expected_headers['x-archive-meta00-scanner']
        tmpdir.chdir()
        test_file = os.path.join(str(tmpdir), 'test.txt')
        with open(test_file, 'w') as fh:
            fh.write('test delete')

        # Non-matching md5, should not delete.
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers,
                 status=400)
        try:
            resp = item.upload(test_file,
                               access_key='test_access',
                               secret_key='test_secret',
                               delete=True,
                               queue_derive=True)
        except Exception as exc:
            assert isinstance(exc, HTTPError)
        assert len(tmpdir.listdir()) == 1

    # Matching md5, should delete.
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        tmpdir.chdir()
        test_file = os.path.join(str(tmpdir), 'test.txt')
        with open(test_file, 'w') as fh:
            fh.write('test delete')

        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers,
                 status=200)
        resp = item.upload(test_file,
                           access_key='test_access',
                           secret_key='test_secret',
                           delete=True,
                           queue_derive=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            del headers['content-type']
            assert headers == _expected_headers
            assert len(tmpdir.listdir()) == 0


def test_upload_checksum(tmpdir):
    s, item, item_metadata = get_session_and_item()
    with responses.RequestsMock() as rsps:
        _expected_headers = deepcopy(EXPECTED_S3_HEADERS)
        del _expected_headers['x-archive-meta00-scanner']

        test_file = os.path.join(str(tmpdir), 'checksum_test.txt')
        with open(test_file, 'w') as fh:
            fh.write('test delete')

        # No skip.
        rsps.add(responses.PUT, S3_URL_RE,
                 adding_headers=_expected_headers,
                 status=200)
        resp = item.upload(test_file,
                           access_key='test_access',
                           secret_key='test_secret',
                           checksum=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            del headers['content-type']
            assert headers == _expected_headers
            assert r.status_code == 200

        # Skip.
        item.item_metadata['files'].append(
            dict(name=u'checksum_test.txt',
                 md5=u'33213e7683c1e6d15b2a658f3c567717'))
        resp = item.upload(test_file,
                           access_key='test_access',
                           secret_key='test_secret',
                           checksum=True)
        for r in resp:
            headers = dict((k.lower(), str(v)) for k, v in r.headers.items())
            assert r.status_code is None


# modify_metadata() ______________________________________________________________________
def test_modify_metadata():
    s, item, item_metadata = get_session_and_item()

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST, 'http://archive.org/metadata/nasa',
                 status=200)

        # Test simple add.
        md = {'foo': 'bar', 'foo11': 'bar'}
        r = item.modify_metadata(md, debug=True)
        p = r.prepare()
        expected_data = {
            'priority': 0,
            '-target': 'metadata',
            '-patch':
            '[{"add": "/foo", "value": "bar"}, {"add": "/foo11", "value": "bar"}]'
        }
        assert p.data == expected_data

        # Test no changes.
        md = {'title': 'NASA Images'}
        r = item.modify_metadata(md, debug=True)
        p = r.prepare()
        expected_data = {'priority': 0, '-target': 'metadata', '-patch': '[]'}
        assert p.data == expected_data

        md = {'title': 'REMOVE_TAG'}
        r = item.modify_metadata(md, debug=True)
        p = r.prepare()
        expected_data = {
            'priority': 0,
            '-target': 'metadata',
            '-patch': '[{"remove": "/title"}]'
        }
        assert p.data == expected_data

        # Test add array.
        md = {'subject': ['one', 'two', 'last']}
        r = item.modify_metadata(md, debug=True)
        p = r.prepare()
        expected_data = {
            'priority': 0,
            '-target': 'metadata',
            '-patch': '[{"add": "/subject", "value": ["one", "two", "last"]}]'
        }
        assert p.data == expected_data

        # Test indexed mod.
        item.item_metadata['metadata']['subject'] = ['first', 'middle', 'last']
        md = {'subject[2]': 'new first'}
        r = item.modify_metadata(md, debug=True)
        p = r.prepare()
        expected_data = {
            'priority': 0,
            '-target': 'metadata',
            '-patch': '[{"value": "new first", "replace": "/subject/2"}]'
        }
        assert p.data == expected_data

        # Test priority.
        md = {'title': 'NASA Images'}
        r = item.modify_metadata(md, priority=3, debug=True)
        p = r.prepare()
        expected_data = {'priority': 3, '-target': 'metadata', '-patch': '[]'}
        assert p.data == expected_data

        # Test auth.
        md = {'title': 'NASA Images'}
        r = item.modify_metadata(md,
                                 access_key='test_access',
                                 secret_key='test_secret',
                                 debug=True)
        p = r.prepare()
        expected_data = {'priority': 0, '-target': 'metadata', '-patch': '[]'}
        assert r.auth.access_key == 'test_access'
        assert r.auth.secret_key == 'test_secret'

        # Test change.
        md = {'title': 'new title'}
        _item_metadata = json.loads(item_metadata)
        _item_metadata['metadata']['title'] = 'new title'
        _item_metadata = json.dumps(_item_metadata)
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                      body=_item_metadata,
                      status=200)
        r = item.modify_metadata(md,
                                  access_key='test_access',
                                  secret_key='test_secret')
        # Test that item re-initializes
        assert item.metadata['title'] == 'new title'
