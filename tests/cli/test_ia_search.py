import responses

from internetarchive.utils import json
from tests.conftest import PROTOCOL, IaRequestsMock, ia_call, load_test_data_file


def test_ia_search_itemlist(capsys):
    test_scrape_response = load_test_data_file('scrape_response.json')

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        url1 = (f'{PROTOCOL}//archive.org/services/search/v1/scrape'
                '?q=collection%3Aattentionkmartshoppers'
                '&count=10000')
        url2 = (f'{PROTOCOL}//archive.org/services/search/v1/scrape?'
                'cursor=W3siaWRlbnRpZmllciI6IjE5NjEtTC0wNTkxNCJ9XQ%3D%3D'
                '&q=collection%3Aattentionkmartshoppers'
                '&count=10000')
        rsps.add(responses.POST, url1,
                 body=test_scrape_response,
                 match_querystring=True)
        _j = json.loads(test_scrape_response)
        del _j['cursor']
        _r = json.dumps(_j)
        rsps.add(responses.POST, url2,
                 body=_r,
                 match_querystring=True)
        ia_call(['ia', 'search', 'collection:attentionkmartshoppers', '--itemlist'])

    out, err = capsys.readouterr()
    assert len(set(out.split())) == 100


def test_ia_search_num_found(capsys):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        url = (f'{PROTOCOL}//archive.org/services/search/v1/scrape'
               '?q=collection%3Anasa&total_only=true'
               '&count=10000')
        rsps.add(responses.POST, url,
                 body='{"items":[],"count":0,"total":50}',
                 match_querystring=True)

        ia_call(['ia', 'search', 'collection:nasa', '--num-found'])
    out, err = capsys.readouterr()
    assert out == '50\n'
