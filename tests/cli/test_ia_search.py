import responses

from internetarchive.utils import json
from tests.conftest import PROTOCOL, IaRequestsMock, ia_call, load_test_data_file


def test_ia_search_itemlist(capsys):
    test_scrape_response = load_test_data_file('scrape_response.json')

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        url = f'{PROTOCOL}//archive.org/services/search/v1/scrape'
        p1 = {
            'q': 'collection:attentionkmartshoppers',
            'count': '10000'
        }
        _j = json.loads(test_scrape_response)
        del _j['cursor']
        _r = json.dumps(_j)
        rsps.add(responses.POST, url,
                 body=_r,
                 match=[responses.matchers.query_param_matcher(p1)])
        ia_call(['ia', 'search', 'collection:attentionkmartshoppers', '--itemlist'])

    out, err = capsys.readouterr()
    assert len(set(out.split())) == 100


def test_ia_search_num_found(capsys):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        url = f'{PROTOCOL}//archive.org/services/search/v1/scrape'
        p = {
            'q': 'collection:nasa',
            'total_only': 'true',
            'count': '10000'
        }
        rsps.add(responses.POST, url,
                 body='{"items":[],"count":0,"total":50}',
                 match=[responses.matchers.query_param_matcher(p)])

        ia_call(['ia', 'search', 'collection:nasa', '--num-found'])
    out, err = capsys.readouterr()
    assert out == '50\n'
