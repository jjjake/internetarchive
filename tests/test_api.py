import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import shutil
from time import time
import json
from copy import deepcopy
import re

import pytest
import responses

import internetarchive.config
from internetarchive import get_session
from internetarchive import get_item
from internetarchive import get_files
from internetarchive import modify_metadata
from internetarchive import upload
from internetarchive import download
from internetarchive import delete
from internetarchive import get_tasks
from internetarchive import search_items


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')

with open(TEST_JSON_FILE, 'r') as fh:
    ITEM_METADATA = fh.read().strip().decode('utf-8')

SEARCH_RESPONSE = {
    "responseHeader": {
        "status":0,
        "QTime":1,
        "params": {
            "json.wrf": "callback",
            "wt":"json",
            "rows":"50",
            "qin":"identifier:nasa",
            "fl":"identifier",
            "start":"0",
            "q":"identifier:nasa"
        }
    },
    "response": {
        "numFound":1,
        "start":0,
        "docs":[
            {"identifier":"nasa"}
        ]
    }
}


# get_session() __________________________________________________________________________
def test_get_session_with_config():
    s = get_session(config={'s3': {'access': 'key'}})
    assert s.access_key == 'key'


def test_get_session_with_config_file(tmpdir):
    tmpdir.chdir()
    test_conf = """[s3]\naccess = key2"""
    with open('ia_test.ini', 'w') as fh:
        fh.write(test_conf)
    s = get_session(config_file='ia_test.ini')
    assert s.access_key == 'key2'


# get_item() _____________________________________________________________________________
def test_get_item():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa')
        assert item.identifier == 'nasa'


def test_get_item_with_config():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa', config={'s3': {'access': 'key'}})
        assert item.session.access_key == 'key'


def test_get_item_with_config_file(tmpdir):
    tmpdir.chdir()
    test_conf = """[s3]\naccess = key2"""
    with open('ia_test.ini', 'w') as fh:
        fh.write(test_conf)
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa', config_file='ia_test.ini')
        assert item.session.access_key == 'key2'


def test_get_item_with_archive_session():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        s = get_session(config={'s3': {'access': 'key3'}})
        item = get_item('nasa', archive_session=s)
        assert item.session.access_key == 'key3'


def test_get_item_with_kwargs():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa', http_adapter_kwargs={'max_retries': 13})
        assert item.session.adapters['http://'].max_retries.total == 13

    try:
        item = get_item('nasa', request_kwargs={'timeout': .0000000000001})
    except Exception as exc:
        assert 'Connection to archive.org timed out' in str(exc)


# get_files() ____________________________________________________________________________
def test_get_files():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        files = get_files('nasa')
        expected_files = set([
            'NASAarchiveLogo.jpg',
            'globe_west_540.jpg',
            'nasa_reviews.xml',
            'nasa_meta.xml',
            'nasa_archive.torrent',
            'nasa_files.xml',
        ])
        assert set([f.name for f in files]) == expected_files


def test_get_files_with_get_item_kwargs(tmpdir):
    tmpdir.chdir()
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        s = get_session(config={'s3': {'access': 'key'}})
        files = get_files('nasa', files='nasa_meta.xml', archive_session=s)
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'

        files = get_files('nasa',
                          files='nasa_meta.xml',
                          config={'logging': {'level': 'INFO'}})
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'

        test_conf = """[s3]\naccess = key2"""
        with open('ia_test.ini', 'w') as fh:
            fh.write(test_conf)
        files = get_files('nasa', files='nasa_meta.xml', config_file='ia_test.ini')
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'

        files = get_files('nasa',
                          files='nasa_meta.xml',
                          http_adapter_kwargs={'max_retries': 3})
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'

        files = get_files('nasa', files='nasa_meta.xml', request_kwargs={'timeout': 4})
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'


def test_get_files_non_existing():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        files = get_files('nasa', files='none')
        assert list(files) == []


def test_get_files_multiple():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        _files = ['nasa_meta.xml', 'nasa_files.xml']
        files = get_files('nasa', files=_files)
        for f in files:
            assert f.name in _files

def test_get_files_source():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        files = get_files('nasa', source='original')
        expected_files = set(['NASAarchiveLogo.jpg', 'globe_west_540.jpg'])
        assert set([f.name for f in files]) == expected_files

        files = get_files('nasa', source=['original', 'metadata'])
        expected_files = set([
            'NASAarchiveLogo.jpg',
            'globe_west_540.jpg',
            'nasa_meta.xml',
            'nasa_files.xml',
            'nasa_reviews.xml',
            'nasa_archive.torrent',
        ])
        assert set([f.name for f in files]) == expected_files


def test_get_files_formats():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        files = get_files('nasa', formats='JPEG')
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'globe_west_540.jpg'

        files = get_files('nasa', formats=['JPEG', 'Collection Header'])
        expected_files = set([
            'globe_west_540.jpg',
            'NASAarchiveLogo.jpg',
        ])
        assert set([f.name for f in files]) == expected_files


def test_get_files_glob_pattern():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        files = get_files('nasa', glob_pattern='*torrent')
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_archive.torrent'

        files = get_files('nasa', glob_pattern='*torrent|*jpg')
        expected_files = set([
            'globe_west_540.jpg',
            'NASAarchiveLogo.jpg',
            'nasa_archive.torrent',
        ])
        assert set([f.name for f in files]) == expected_files


# modify_metadata() ______________________________________________________________________
def test_modify_metadata():
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/test',
                 body={},
                 status=200)
        rsps.add(responses.POST, 'http://archive.org/metadata/test',
                 body='{"success":true,"task_id":423444944,"log":"https://catalogd.archive.org/log/423444944"}',
                 status=200)
        r = modify_metadata('test', dict(foo=1))
        assert r.status_code == 200
        assert r.json() == {u'task_id': 423444944, u'success': True, u'log': u'https://catalogd.archive.org/log/423444944'}


# upload() _______________________________________________________________________________
def test_upload():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        expected_s3_headers = {
            'content-length': '7557',
            'x-archive-queue-derive': '1',
            'x-archive-meta00-scanner': 'uri(Internet%20Archive%20Python%20library',
            'x-archive-size-hint': '7557',
            'content-md5': '6f1834f5c70c0eabf93dea675ccf90c4',
            'x-archive-auto-make-bucket': '1',
            'authorization': 'LOW test_access:test_secret',
        }
        rsps.add(responses.PUT, re.compile(r'.*s3.us.archive.org/.*'),
                 adding_headers=expected_s3_headers,
                 status=200)
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body={},
                 status=200)
        resp = upload('nasa', TEST_JSON_FILE, debug=True, access_key='test_access', secret_key='test_secret')
        for r in resp:
            p = r.prepare()
            headers = dict((k.lower(), str(v)) for k, v in p.headers.items())
            scanner_header = '%20'.join(
                r.headers['x-archive-meta00-scanner'].split('%20')[:4])
            headers['x-archive-meta00-scanner'] = scanner_header
            assert headers == expected_s3_headers
            assert p.url == 'http://s3.us.archive.org/nasa/nasa_meta.json'


# download() _____________________________________________________________________________
def test_download(tmpdir):
    tmpdir.chdir()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/download/nasa/nasa_meta.xml',
                 body='test content',
                 status=200)
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)
        r = download('nasa', 'nasa_meta.xml')
        p = os.path.join(str(tmpdir), 'nasa')
        assert len(os.listdir(p)) == 1
        with open('nasa/nasa_meta.xml') as fh:
            assert fh.read() == 'test content'


# delete() _______________________________________________________________________________
def test_delete():
    pass


# get_tasks() ____________________________________________________________________________
def test_get_tasks():
    pass


# search_items() _________________________________________________________________________
def test_search_items():
    search_response_str = json.dumps(SEARCH_RESPONSE)
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php',
                 body=search_response_str,
                 status=200)
        r = search_items('identifier:nasa')
        assert r.num_found == 1
        assert list(r) == [{'identifier': 'nasa'}]


def test_search_items_with_fields():
    search_r = deepcopy(SEARCH_RESPONSE)
    search_r['response']['docs'] = [
        {'identifier': 'nasa', 'title': 'NASA Images'}
    ]
    search_response_str = json.dumps(search_r)
    with responses.RequestsMock(
        assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php',
                 body=search_response_str,
                 status=200)
        r = search_items('identifier:nasa', fields=['identifier', 'title'])
        assert r.num_found == 1
        assert list(r) == [{'identifier': 'nasa', 'title': 'NASA Images'}]
