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


if sys.version_info < (2, 7, 9):
    protocol = 'http:'
else:
    protocol = 'https:'


TESTS_DIR = os.path.join(os.path.dirname(__file__), os.pardir)
TEST_JSON_FILE = os.path.join(TESTS_DIR, 'data/advanced_search_response.json')
with open(TEST_JSON_FILE) as fh:
    TEST_SEARCH_RESPONSE = fh.read()


def test_ia_search_sort_asc(capsys):
    url1 = ('{0}//archive.org/advancedsearch.php?q=collection%3Anasa&output=json&'
            'rows=0&sort%5B0%5D=identifier+asc'.format(protocol))
    url2 = ('{0}//archive.org/advancedsearch.php?q=collection%3Anasa&output=json&'
            'rows=250&sort%5B0%5D=identifier+asc&page=1'.format(protocol))
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
    url1 = ('{0}//archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=0&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier'.format(protocol))
    url2 = ('{0}//archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=25&page=1&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier'.format(protocol))
    url3 = ('{0}//archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=25&page=2&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier'.format(protocol))
    url4 = ('{0}//archive.org/advancedsearch.php?'
            'q=collection%3Anasa&output=json&rows=25&page=3&sort%5B0%5D=identifier+asc&'
            'fl%5B0%5D=identifier'.format(protocol))
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
        url1 = ('{0}//archive.org/advancedsearch.php?'
                'q=collection%3Aattentionkmartshoppers&output=json&rows=0&'
                'sort%5B0%5D=identifier+asc&fl%5B0%5D=identifier'.format(protocol))
        url2 = ('{0}//archive.org/advancedsearch.php?'
                'fl%5B0%5D=identifier&rows=250&sort%5B0%5D=identifier+asc&q=collection%3'
                'Aattentionkmartshoppers&output=json&page=1'.format(protocol))
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
        url = ('{0}//archive.org/advancedsearch.php?q=collection%3Anasa&output=json&'
               'rows=0&sort%5B0%5D=identifier+asc'.format(protocol))
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
