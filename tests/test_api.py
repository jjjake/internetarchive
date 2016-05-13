from __future__ import unicode_literals
import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import json
from copy import deepcopy
import re

import six
import pytest
import responses
from requests.packages import urllib3

from internetarchive import get_session
from internetarchive import get_item
from internetarchive import get_files
from internetarchive import modify_metadata
from internetarchive import upload
from internetarchive import download
from internetarchive import search_items


protocol = 'https:'


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')
PY3 = six.PY3

with open(TEST_JSON_FILE, 'r') as fh:
    ITEM_METADATA = fh.read().strip()

ROOT_DIR = os.getcwd()
TEST_JSON_SEARCH_FILE = os.path.join(ROOT_DIR, 'tests/data/advanced_search_response.json')
with open(TEST_JSON_SEARCH_FILE) as fh:
    TEST_SEARCH_RESPONSE = fh.read()
TEST_JSON_SCRAPE_FILE = os.path.join(ROOT_DIR, 'tests/data/scrape_response.json')
with open(TEST_JSON_SCRAPE_FILE) as fh:
    TEST_SCRAPE_RESPONSE = fh.read()
    _j = json.loads(TEST_SCRAPE_RESPONSE)
    del _j['cursor']
    _j['items'] = [{'identifier': 'nasa'}]
    TEST_SCRAPE_RESPONSE = json.dumps(_j)


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


def test_get_item():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa')
        assert item.identifier == 'nasa'


def test_get_item_with_config():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
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
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa', config_file='ia_test.ini')
        assert item.session.access_key == 'key2'


def test_get_item_with_archive_session():
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        s = get_session(config={'s3': {'access': 'key3'}})
        item = get_item('nasa', archive_session=s)
        assert item.session.access_key == 'key3'


def test_get_item_with_kwargs():
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        item = get_item('nasa', http_adapter_kwargs={'max_retries': 13})
        assert isinstance(item.session.adapters['{0}//'.format(protocol)].max_retries,
                          urllib3.Retry)

    try:
        item = get_item('nasa', request_kwargs={'timeout': .0000000000001})
    except Exception as exc:
        assert 'Connection to archive.org timed out' in str(exc)


def test_get_files():
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
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
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
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
        files = get_files('nasa', files='nasa_meta.xml',
                          config_file='ia_test.ini')
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'

        files = get_files('nasa',
                          files='nasa_meta.xml',
                          http_adapter_kwargs={'max_retries': 3})
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'

        files = get_files('nasa', files='nasa_meta.xml',
                          request_kwargs={'timeout': 4})
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_meta.xml'


def test_get_files_non_existing():
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        files = get_files('nasa', files='none')
        assert list(files) == []


def test_get_files_multiple():
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        _files = ['nasa_meta.xml', 'nasa_files.xml']
        files = get_files('nasa', files=_files)
        for f in files:
            assert f.name in _files


def test_get_files_formats():
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
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
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
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


@pytest.mark.skipif('PY3 is True', reason='responses not working with PY3.')
def test_modify_metadata():
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/test'.format(protocol),
                 body={},
                 status=200)
        rsps.add(responses.POST, '{0}//archive.org/metadata/test'.format(protocol),
                 body=('{"success":true,"task_id":423444944,'
                       '"log":"https://catalogd.archive.org/log/423444944"}'),
                 status=200)
        r = modify_metadata('test', dict(foo=1))
        assert r.status_code == 200
        assert r.json() == {
            'task_id': 423444944,
            'success': True,
            'log': 'https://catalogd.archive.org/log/423444944'
        }


@pytest.mark.skipif('PY3 is True', reason='responses not working with PY3.')
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
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body={},
                 status=200)
        resp = upload('nasa', TEST_JSON_FILE,
                      debug=True,
                      access_key='test_access',
                      secret_key='test_secret')
        for r in resp:
            p = r.prepare()
            headers = dict((k.lower(), str(v)) for k, v in p.headers.items())
            scanner_header = '%20'.join(
                r.headers['x-archive-meta00-scanner'].split('%20')[:4])
            headers['x-archive-meta00-scanner'] = scanner_header
            assert headers == expected_s3_headers
            assert p.url == '{0}//s3.us.archive.org/nasa/nasa_meta.json'.format(
                protocol)


def test_download(tmpdir):
    tmpdir.chdir()
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET,
                 '{0}//archive.org/download/nasa/nasa_meta.xml'.format(
                     protocol),
                 body='test content',
                 status=200)
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        download('nasa', 'nasa_meta.xml')
        p = os.path.join(str(tmpdir), 'nasa')
        assert len(os.listdir(p)) == 1
        with open('nasa/nasa_meta.xml') as fh:
            assert fh.read() == 'test content'


def test_delete():
    pass


def test_get_tasks():
    pass


def test_search_items():
    _j = json.loads(TEST_SEARCH_RESPONSE)
    _j['response']['numFound'] = 1
    _search_r = json.dumps(_j)
    results_url = ('{0}//archive.org/services/search/beta/scrape.php'
                   '?q=identifier%3Anasa&size=10000&REQUIRE_AUTH=true'.format(protocol))
    count_url = ('{0}//archive.org/services/search/beta/scrape.php'
                 '?q=identifier%3Anasa&total_only=true&REQUIRE_AUTH=true'
                 '&size=10000'.format(protocol))
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST, results_url,
                 body=TEST_SCRAPE_RESPONSE,
                 match_querystring=True,
                 status=200)
        rsps.add(responses.POST, count_url,
                 body='{"items":[],"count":0,"total":1}',
                 match_querystring=True,
                 content_type='application/json; charset=UTF-8',
                 status=200)
        r = search_items('identifier:nasa')
        expected_results = [{'identifier': 'nasa'}]
        assert r.num_found == 1
        assert iter(r).search == r
        assert len(iter(r)) == 1
        assert len(r.iter_as_results()) == 1
        assert list(r) == expected_results
        assert list(r.iter_as_results()) == expected_results


def test_search_items_with_fields():
    _j = json.loads(TEST_SCRAPE_RESPONSE)
    _j['items'] = [
        {'identifier': 'nasa', 'title': 'NASA Images'}
    ]
    search_response_str = json.dumps(_j)
    results_url = ('{0}//archive.org/services/search/beta/scrape.php'
                   '?q=identifier%3Anasa&size=10000&REQUIRE_AUTH=true'
                   '&fields=identifier%2Ctitle'.format(protocol))
    count_url = ('{0}//archive.org/services/search/beta/scrape.php'
                 '?q=identifier%3Anasa&total_only=true&REQUIRE_AUTH=true'
                 '&size=10000'.format(protocol))
    with responses.RequestsMock() as rsps:
        rsps.add(responses.POST, results_url,
                 match_querystring=True,
                 body=search_response_str,
                 status=200)
        rsps.add(responses.POST, count_url,
                 body='{"items":[],"count":0,"total":1}',
                 match_querystring=True,
                 content_type='application/json; charset=UTF-8',
                 status=200)
        r = search_items('identifier:nasa', fields=['identifier', 'title'])
        assert list(r) == [{'identifier': 'nasa', 'title': 'NASA Images'}]


def test_search_items_as_items():
    search_response_str = json.dumps(TEST_SCRAPE_RESPONSE)
    with responses.RequestsMock(
            assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST,
                 '{0}//archive.org/services/search/beta/scrape.php'.format(protocol),
                 body=TEST_SCRAPE_RESPONSE,
                 status=200)
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        r = search_items('identifier:nasa')
        assert [x.identifier for x in r.iter_as_items()] == ['nasa']
        assert r.iter_as_items().search == r


def test_page_row_specification():
    _j = json.loads(TEST_SEARCH_RESPONSE)
    _j['response']['docs'] = [{'identifier': 'nasa'}]
    _j['response']['numFound'] = 1
    _search_r = json.dumps(_j)
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/advancedsearch.php'.format(protocol),
                 body=_search_r,
                 status=200)
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=ITEM_METADATA,
                 status=200)
        rsps.add(responses.POST, 'https://archive.org/services/search/beta/scrape.php',
                 body='{"items":[],"count":0,"total":1}',
                 match_querystring=False,
                 content_type='application/json; charset=UTF-8',
                 status=200)
        r = search_items('identifier:nasa', params={
                         'page': '1', 'rows': '1'})
        assert [x.identifier for x in r.iter_as_items()] == ['nasa']
        assert r.iter_as_items().search == r
        assert len(r.iter_as_items()) == 1
