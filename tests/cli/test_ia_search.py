import sys

import pytest
import responses

from internetarchive.cli import ia
from internetarchive.cli.ia_search import fts_hit_identifiers
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


# Trimmed from real ``POST /ia-pub-fts-api`` responses for the request
# ``{"q": "computer", "size": "10000", "from": "0", "scroll": true}`` (page 1),
# then the same request with the returned ``scroll_id`` (page 2), made on
# 2026-11-12. Page 1 hits carry ``fields`` (identifier as a list); page 2 hits
# carry ``_source`` (identifier as a plain string) and no ``fields``.
FTS_PAGE_1_HIT = {
    '_index': 'fts_main_v2',
    '_id': 'manualzilla-id-7056964|f99791c3172853fd2068d463e83a14f0ca55446f',
    '_score': 3.866792,
    'highlight': {'text': ['the {{{computer}}}.']},
    'fields': {
        'identifier': ['manualzilla-id-7056964'],
        'filename': ['7056964_hocr_searchtext.txt.gz'],
    },
}
FTS_PAGE_2_HIT = {
    '_index': 'fts_main_v2',
    '_id': 'manualsbase-id-247624|1039d0366f2d4c0ab76d74993a097b5c0ca1319f',
    '_score': 3.8494558,
    'highlight': {'text': ['of the {{{computer}}}.']},
    '_source': {
        'identifier': 'manualsbase-id-247624',
        'filename': '247624_abbyy.gz',
    },
}
# Neither ``fields`` nor ``_source``: only the ``_id`` identifies the item.
FTS_ID_ONLY_HIT = {
    '_index': 'fts_main_v2',
    '_id': 'idonly-item|0123456789abcdef0123456789abcdef01234567',
    '_score': 3.0,
}


def _fts_page(hits, scroll_id='scroll-1'):
    return {'_scroll_id': scroll_id, 'hits': {'total': len(hits), 'hits': hits}}


def test_ia_search_fts_itemlist_scroll_page_with_source_hits(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=_fts_page([FTS_PAGE_1_HIT]))
        rsps.add(
            responses.POST,
            FTS_URL,
            json=_fts_page([FTS_PAGE_2_HIT, FTS_ID_ONLY_HIT], 'scroll-2'),
        )
        rsps.add(responses.POST, FTS_URL, json=_fts_page([], 'scroll-3'))
        ia_call(['ia', 'search', '--fts', 'computer', '--itemlist'])

    out, err = capsys.readouterr()
    assert out.splitlines() == [
        'manualzilla-id-7056964',
        'manualsbase-id-247624',
        'idonly-item',
    ]
    assert err == ''


def test_ia_search_fts_itemlist_hit_without_any_identifier_is_skipped(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(
            responses.POST,
            FTS_URL,
            json=_fts_page([{'_index': 'fts_main_v2', '_score': 1.0}, FTS_PAGE_1_HIT]),
        )
        rsps.add(responses.POST, FTS_URL, json=_fts_page([], 'scroll-2'))
        ia_call(['ia', 'search', '--fts', 'computer', '--itemlist'])

    out, _err = capsys.readouterr()
    assert out.splitlines() == ['manualzilla-id-7056964']


@pytest.mark.parametrize(
    ('hit', 'expected'),
    [
        (FTS_PAGE_1_HIT, ['manualzilla-id-7056964']),
        (FTS_PAGE_2_HIT, ['manualsbase-id-247624']),
        (FTS_ID_ONLY_HIT, ['idonly-item']),
        ({'fields': {'identifier': ['a', 'b']}}, ['a', 'b']),
        ({'fields': {}, '_source': {'identifier': 'src'}, '_id': 'x|y'}, ['src']),
        ({'fields': {'identifier': ['']}, '_id': 'x|y'}, ['x']),
        ({'fields': [], '_source': 'oops', '_id': 'noseparator'}, ['noseparator']),
        ({'_id': '|abc'}, []),
        ({'_id': None}, []),
        ({}, []),
        (None, []),
    ],
)
def test_fts_hit_identifiers(hit, expected):
    assert fts_hit_identifiers(hit) == expected


def test_ia_search_fts_dsl_itemlist_scroll_page_with_source_hits(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=_fts_page([FTS_PAGE_2_HIT]))
        rsps.add(responses.POST, FTS_URL, json=_fts_page([], 'scroll-2'))
        ia_call(['ia', 'search', '--dsl-fts', 'computer', '--itemlist'])

    out, _err = capsys.readouterr()
    assert out.splitlines() == ['manualsbase-id-247624']
