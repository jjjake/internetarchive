try:
    import ujson as json
except ImportError:
    import json
import types
import sys
import re
import os
from copy import deepcopy
import shutil

import pytest
import responses

from internetarchive.cli import ia


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/advanced_search_response.json')
with open(TEST_JSON_FILE) as fh:
    TEST_SEARCH_RESPONSE = fh.read()


def test_ia_search_sort_asc(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=0&sort%5B0%5D=identifier+asc',
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&sort%5B0%5D=identifier+asc&output=json&rows=100&page=1',
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '--sort', 'identifier:asc']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    j = json.loads(TEST_SEARCH_RESPONSE)
    expected_output = '\n'.join([json.dumps(d) for d in j['response']['docs']]) + '\n'
    assert out == expected_output


def test_ia_search_multi_page(capsys):
    j = json.loads(TEST_SEARCH_RESPONSE)
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=0&fl%5B0%5D=identifier',
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)
        _j = deepcopy(j)
        _j['response']['docs'] = j['response']['docs'][:25] 
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=25&page=1&fl%5B0%5D=identifier',
                 body=json.dumps(_j),
                 status=200,
                 match_querystring=True)
        _j = deepcopy(j)
        _j['response']['docs'] = j['response']['docs'][25:] 
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=25&page=2&fl%5B0%5D=identifier',
                 body=json.dumps(_j),
                 status=200,
                 match_querystring=True)
        _j = deepcopy(j)
        _j['response']['docs'] = []
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=25&page=3&fl%5B0%5D=identifier',
                 body=json.dumps(_j),
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '-p', 'rows:25', '-f', 'identifier']
        try:
            r = ia.main()
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
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=0',
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=100&page=1',
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '--itemlist']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    out, err = capsys.readouterr()
    j = json.loads(TEST_SEARCH_RESPONSE)
    expected_output = '\n'.join([d['identifier'] for d in j['response']['docs']]) + '\n'
    assert out == expected_output


def test_ia_search_num_found(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/advancedsearch.php?q=collection%3Anasa&output=json&rows=0',
                 body=TEST_SEARCH_RESPONSE,
                 status=200,
                 match_querystring=True)

        sys.argv = ['ia', 'search', 'collection:nasa', '--num-found']
        try:
            r = ia.main()
        except SystemExit as exc:
            assert not exc.code

    #j = json.loads(TEST_SEARCH_RESPONSE)
    out, err = capsys.readouterr()
    assert out == '50\n'
