import os
import re

import responses
import urllib3

from internetarchive import (
    download,
    get_files,
    get_item,
    get_session,
    modify_metadata,
    search_items,
    upload,
)
from internetarchive.utils import InvalidIdentifierException, json
from tests.conftest import (
    NASA_METADATA_PATH,
    PROTOCOL,
    IaRequestsMock,
    load_file,
    load_test_data_file,
)

TEST_SEARCH_RESPONSE = load_test_data_file('advanced_search_response.json')
TEST_SCRAPE_RESPONSE = load_test_data_file('scrape_response.json')
_j = json.loads(TEST_SCRAPE_RESPONSE)
del _j['cursor']
_j['items'] = [{'identifier': 'nasa'}]
_j['total'] = 1
TEST_SCRAPE_RESPONSE = json.dumps(_j)


def test_get_session_with_config():
    s = get_session(config={'s3': {'access': 'key'}, 'gengeral': {'secure': False}})
    assert s.access_key == 'key'


def test_get_session_with_config_file(tmpdir):
    tmpdir.chdir()
    test_conf = '[s3]\naccess = key2'
    with open('ia_test.ini', 'w') as fh:
        fh.write(test_conf)
    s = get_session(config_file='ia_test.ini')
    assert s.access_key == 'key2'


def test_get_item(nasa_mocker):
    item = get_item('nasa')
    assert item.identifier == 'nasa'


def test_get_item_with_config(nasa_mocker):
    item = get_item('nasa', config={'s3': {'access': 'key'}})
    assert item.session.access_key == 'key'


def test_get_item_with_config_file(tmpdir, nasa_mocker):
    tmpdir.chdir()
    test_conf = '[s3]\naccess = key2'
    with open('ia_test.ini', 'w') as fh:
        fh.write(test_conf)

    item = get_item('nasa', config_file='ia_test.ini')
    assert item.session.access_key == 'key2'


def test_get_item_with_archive_session(nasa_mocker):
    s = get_session(config={'s3': {'access': 'key3'}})
    item = get_item('nasa', archive_session=s)
    assert item.session.access_key == 'key3'


def test_get_item_with_kwargs():
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        item = get_item('nasa', http_adapter_kwargs={'max_retries': 13})
        assert isinstance(item.session.adapters[f'{PROTOCOL}//'].max_retries,
                          urllib3.Retry)

    try:
        get_item('nasa', request_kwargs={'timeout': .0000000000001})
    except Exception as exc:
        assert 'timed out' in str(exc)


def test_get_files():
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        files = get_files('nasa')
        expected_files = {
            'NASAarchiveLogo.jpg',
            'globe_west_540.jpg',
            'nasa_reviews.xml',
            'nasa_meta.xml',
            'nasa_archive.torrent',
            'nasa_files.xml',
        }
        assert {f.name for f in files} == expected_files


def test_get_files_with_get_item_kwargs(tmpdir):
    tmpdir.chdir()
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
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

        test_conf = '[s3]\naccess = key2'
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


def test_get_files_non_existing(nasa_mocker):
    files = get_files('nasa', files='none')
    assert list(files) == []


def test_get_files_multiple(nasa_mocker):
    _files = ['nasa_meta.xml', 'nasa_files.xml']
    files = get_files('nasa', files=_files)
    for f in files:
        assert f.name in _files


def test_get_files_formats():
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        files = get_files('nasa', formats='JPEG')
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'globe_west_540.jpg'

        files = get_files('nasa', formats=['JPEG', 'Collection Header'])
        expected_files = {
            'globe_west_540.jpg',
            'NASAarchiveLogo.jpg',
        }
        assert {f.name for f in files} == expected_files


def test_get_files_glob_pattern():
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        files = get_files('nasa', glob_pattern='*torrent')
        files = list(files)
        assert len(files) == 1
        assert files[0].name == 'nasa_archive.torrent'

        files = get_files('nasa', glob_pattern='*torrent|*jpg')
        expected_files = {
            'globe_west_540.jpg',
            'NASAarchiveLogo.jpg',
            'nasa_archive.torrent',
        }
        assert {f.name for f in files} == expected_files


def test_modify_metadata():
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, f'{PROTOCOL}//archive.org/metadata/nasa',
                 body='{"metadata":{"title":"foo"}}')
        rsps.add(responses.POST, f'{PROTOCOL}//archive.org/metadata/nasa',
                 body=('{"success":true,"task_id":423444944,'
                       '"log":"https://catalogd.archive.org/log/423444944"}'))
        r = modify_metadata('nasa', {'foo': 1})
        assert r.status_code == 200
        assert r.json() == {
            'task_id': 423444944,
            'success': True,
            'log': 'https://catalogd.archive.org/log/423444944'
        }


def test_upload():
    expected_s3_headers = {
        'content-length': '7557',
        'x-archive-queue-derive': '1',
        'x-archive-meta00-scanner': 'uri(Internet%20Archive%20Python%20library',
        'x-archive-size-hint': '7557',
        'x-archive-auto-make-bucket': '1',
        'authorization': 'LOW test_access:test_secret',
    }
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, re.compile(r'.*s3.us.archive.org/.*'),
                 adding_headers=expected_s3_headers)
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, f'{PROTOCOL}//archive.org/metadata/nasa',
                 body='{}')
        _responses = upload('nasa', NASA_METADATA_PATH,
                            access_key='test_access',
                            secret_key='test_secret')
        for response in _responses:
            req = response.request
            headers = {k.lower(): str(v) for k, v in req.headers.items()}
            scanner_header = '%20'.join(
                response.headers['x-archive-meta00-scanner'].split('%20')[:4])
            headers['x-archive-meta00-scanner'] = scanner_header
            assert 'user-agent' in headers
            del headers['accept']
            del headers['accept-encoding']
            del headers['connection']
            del headers['user-agent']
            assert headers == expected_s3_headers
            assert req.url == f'{PROTOCOL}//s3.us.archive.org/nasa/nasa.json'


def test_upload_validate_identifier():
    try:
        upload('føø', NASA_METADATA_PATH,
              access_key='test_access',
              secret_key='test_secret',
              validate_identifier=True)
        raise AssertionError("Given invalid identifier was not correctly validated.")
    except Exception as exc:
        assert isinstance(exc, InvalidIdentifierException)

    expected_s3_headers = {
        'content-length': '7557',
        'x-archive-queue-derive': '1',
        'x-archive-meta00-scanner': 'uri(Internet%20Archive%20Python%20library',
        'x-archive-size-hint': '7557',
        'x-archive-auto-make-bucket': '1',
        'authorization': 'LOW test_access:test_secret',
    }
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.PUT, re.compile(r'.*s3.us.archive.org/.*'),
                 adding_headers=expected_s3_headers)
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, f'{PROTOCOL}//archive.org/metadata/nasa',
                 body='{}')
        upload('nasa', NASA_METADATA_PATH,
              access_key='test_access',
              secret_key='test_secret',
              validate_identifier=True)
        assert True


def test_download(tmpdir):
    tmpdir.chdir()
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET,
                 f'{PROTOCOL}//archive.org/download/nasa/nasa_meta.xml',
                 body='test content')
        rsps.add_metadata_mock('nasa')
        download('nasa', 'nasa_meta.xml')
        p = os.path.join(str(tmpdir), 'nasa')
        assert len(os.listdir(p)) == 1
        assert load_file('nasa/nasa_meta.xml') == 'test content'


def test_search_items(session):
    results_url = (f'{PROTOCOL}//archive.org/services/search/v1/scrape'
                   '?q=identifier%3Anasa&count=10000')
    count_url = (f'{PROTOCOL}//archive.org/services/search/v1/scrape'
                 '?q=identifier%3Anasa&total_only=true'
                 '&count=10000')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST, results_url,
                 body=TEST_SCRAPE_RESPONSE,
                 match_querystring=True)
        rsps.add(responses.POST, count_url,
                 body='{"items":[],"count":0,"total":1}',
                 match_querystring=True,
                 content_type='application/json; charset=UTF-8')
        r = search_items('identifier:nasa', archive_session=session)
        expected_results = [{'identifier': 'nasa'}]
        assert r.num_found == 1
        assert iter(r).search == r
        assert len(iter(r)) == 1
        assert len(r.iter_as_results()) == 1
        assert list(r) == expected_results
        assert list(r.iter_as_results()) == expected_results
        assert r.fts == False


def test_search_items_with_fields(session):
    _j = json.loads(TEST_SCRAPE_RESPONSE)
    _j['items'] = [
        {'identifier': 'nasa', 'title': 'NASA Images'}
    ]
    search_response_str = json.dumps(_j)
    results_url = (f'{PROTOCOL}//archive.org/services/search/v1/scrape'
                   '?q=identifier%3Anasa&count=10000'
                   '&fields=identifier%2Ctitle')
    count_url = (f'{PROTOCOL}//archive.org/services/search/v1/scrape'
                 '?q=identifier%3Anasa&total_only=true'
                 '&count=10000')
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, results_url,
                 match_querystring=True,
                 body=search_response_str)
        rsps.add(responses.POST, count_url,
                 body='{"items":[],"count":0,"total":1}',
                 match_querystring=True,
                 content_type='application/json; charset=UTF-8')
        r = search_items('identifier:nasa', fields=['identifier', 'title'],
                         archive_session=session)
        assert list(r) == [{'identifier': 'nasa', 'title': 'NASA Images'}]


def test_search_items_as_items(session):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST,
                 f'{PROTOCOL}//archive.org/services/search/v1/scrape',
                 body=TEST_SCRAPE_RESPONSE)
        rsps.add_metadata_mock('nasa')
        r = search_items('identifier:nasa', archive_session=session)
        assert [x.identifier for x in r.iter_as_items()] == ['nasa']
        assert r.iter_as_items().search == r


def test_search_items_fts(session):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.POST,
                 f'{PROTOCOL}//be-api.us.archive.org/ia-pub-fts-api',
                 body=TEST_SCRAPE_RESPONSE)
        rsps.add_metadata_mock('nasa')

        r = search_items('nina simone',
                         full_text_search=True,
                         archive_session=session)
        print(r.search_url)
        assert r.fts == True
        assert r.dsl_fts == False
        assert r.query == '!L nina simone'
        assert r.params == {'count': 10000, 'q': '!L nina simone'}

        r = search_items('nina simone',
                         full_text_search=True,
                         dsl_fts=True,
                         archive_session=session)
        assert r.fts == True
        assert r.dsl_fts == True
        assert r.query == 'nina simone'
        assert r.params == {'count': 10000, 'q': 'nina simone'}
        r = search_items('nina simone',
                         dsl_fts=True,
                         archive_session=session)
        assert r.fts == True
        assert r.dsl_fts == True
        assert r.query == 'nina simone'
        assert r.params == {'count': 10000, 'q': 'nina simone'}


def test_page_row_specification(session):
    _j = json.loads(TEST_SEARCH_RESPONSE)
    _j['response']['items'] = [{'identifier': 'nasa'}]
    _j['response']['numFound'] = 1
    _search_r = json.dumps(_j)
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, f'{PROTOCOL}//archive.org/advancedsearch.php',
                 body=_search_r)
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.POST,
                 f'{PROTOCOL}//archive.org/services/search/v1/scrape',
                 body='{"items":[],"count":0,"total":1}',
                 match_querystring=False,
                 content_type='application/json; charset=UTF-8')
        r = search_items('identifier:nasa', params={'page': '1', 'rows': '1'},
                         archive_session=session)
        assert r.iter_as_items().search == r
        assert len(r.iter_as_items()) == 1
