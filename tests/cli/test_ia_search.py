import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
try:
    import ujson as json
except ImportError:
    import json
from copy import deepcopy

import responses

from internetarchive.cli import ia


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/advanced_search_response.json')
with open(TEST_JSON_FILE) as fh:
    TEST_SEARCH_RESPONSE = fh.read()


def test_ia_search_sort_asc(capsys):
    url1 = ('https://archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=0&sort%5B0%5D=identifier+asc')
    url2 = ('https://archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=250&sort%5B0%5D=identifier+asc&page=1')
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, url1,
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)
        rsps.add(responses.GET, url2,
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '--sort', 'identifier:asc']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    j = json.loads(TEST_SEARCH_RESPONSE)
    expected_output = '\n'.join([json.dumps(d) for d in j['response']['docs']]) + '\n'
    assert out == expected_output


def test_ia_search_multi_page(capsys):
    j = json.loads(TEST_SEARCH_RESPONSE)
    url1 = ('https://archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=0&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier')
    url2 = ('https://archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=25&page=1&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier')
    url3 = ('https://archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=25&page=2&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier')
    url4 = ('https://archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=25&page=3&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier')
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, url1,
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)
        _j = deepcopy(j)
        _j['response']['docs'] = j['response']['docs'][:25]
        rsps.add(responses.GET, url2,
                 body=json.dumps(_j),
                 status=200,
                 match_querystring=True)
        _j = deepcopy(j)
        _j['response']['docs'] = j['response']['docs'][25:]
        rsps.add(responses.GET, url3,
                 body=json.dumps(_j),
                 status=200,
                 match_querystring=True)
        _j = deepcopy(j)
        _j['response']['docs'] = []
        rsps.add(responses.GET, url4,
                 body=json.dumps(_j),
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '-p', 'rows:25', '-f',
                    'identifier']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    out_ids = set()
    for l in out.split('\n'):
        if not l:
            continue
        jj = json.loads(l)
        out_ids.add(jj['identifier'])
    expected_out_ids = set([d['identifier'] for d in j['response']['docs']])
    assert out_ids == expected_out_ids


def test_ia_search_itemlist(capsys):
    with responses.RequestsMock() as rsps:
        url1 = ('https://archive.org/advancedsearch.php?'
                'q=collection%3Aattentionkmartshoppers&output=json&rows=0&'
                'sort%5B0%5D=identifier+asc&fl%5B0%5D=identifier')
        url2 = ('https://archive.org/advancedsearch.php?'
                'fl%5B0%5D=identifier&rows=250&sort%5B0%5D=identifier+asc&'
                'q=collection%3Aattentionkmartshoppers&output=json&page=1')
        rsps.add(responses.GET, url1,
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)
        rsps.add(responses.GET, url2,
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:attentionkmartshoppers', '--itemlist']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    j = json.loads(TEST_SEARCH_RESPONSE)
    expected_output = '\n'.join([d['identifier'] for d in j['response']['docs']]) + '\n'
    assert out == expected_output


def test_ia_search_num_found(capsys):
    with responses.RequestsMock() as rsps:
        url = ('https://archive.org/advancedsearch.php?'
               'q=collection%3Anasa&output=json&rows=0&sort%5B0%5D=identifier+asc')
        rsps.add(responses.GET, url,
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '--num-found']
        try:
            ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    assert out == '50\n'
