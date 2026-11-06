import sys

import pytest
import responses

from internetarchive.cli import ia
from internetarchive.utils import json
from tests.conftest import (
    PROTOCOL,
    TEST_CONFIG,
    IaRequestsMock,
    ia_call,
    load_test_data_file,
)


def test_ia_search_itemlist(capsys):
    test_scrape_response = load_test_data_file('scrape_response.json')

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        url = f'{PROTOCOL}//archive.org/services/search/v1/scrape'
        p1 = {'q': 'collection:attentionkmartshoppers', 'count': '10000'}
        _j = json.loads(test_scrape_response)
        del _j['cursor']
        _r = json.dumps(_j)
        rsps.add(
            responses.POST,
            url,
            body=_r,
            match=[responses.matchers.query_param_matcher(p1)],
        )
        ia_call(['ia', 'search', 'collection:attentionkmartshoppers', '--itemlist'])

    out, _err = capsys.readouterr()
    assert len(set(out.split())) == 100


def test_ia_search_num_found(capsys):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        url = f'{PROTOCOL}//archive.org/services/search/v1/scrape'
        p = {'q': 'collection:nasa', 'total_only': 'true', 'count': '10000'}
        rsps.add(
            responses.POST,
            url,
            body='{"items":[],"count":0,"total":50}',
            match=[responses.matchers.query_param_matcher(p)],
        )

        ia_call(['ia', 'search', 'collection:nasa', '--num-found'])
    out, _err = capsys.readouterr()
    assert out == '50\n'


FTS_URL = f'{PROTOCOL}//be-api.us.archive.org/ia-pub-fts-api'


def test_ia_search_fts_server_error_exits_nonzero(capsys, monkeypatch):
    error_body = {
        'user_message': {
            'msg_type': 'ERROR',
            'text': 'the parameter scroll must be a boolean',
        },
        'ia-pub-fts-api-wrapper': True,
    }
    # Call ia.main() directly: ia_call() only checks the exit code when
    # SystemExit is raised, and this test must fail if it is not.
    argv = ['ia', '--config-file', TEST_CONFIG, 'search', '--fts', 'computer']
    monkeypatch.setattr(sys, 'argv', argv)
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=error_body, status=400)
        with pytest.raises(SystemExit) as exc_info:
            ia.main()
    assert exc_info.value.code == 1

    out, err = capsys.readouterr()
    assert out == ''
    assert 'the parameter scroll must be a boolean' in err


def test_ia_search_fts_empty_result_exits_zero(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(
            responses.POST,
            FTS_URL,
            json={'_scroll_id': 's', 'hits': {'total': 0, 'hits': []}},
        )
        ia_call(['ia', 'search', '--fts', 'computer'])

    out, err = capsys.readouterr()
    assert out == ''
    assert err == ''
