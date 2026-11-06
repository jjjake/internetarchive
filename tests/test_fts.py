"""Tests for full-text search (``Search._full_text_search``).

The FTS API at ``be-api.us.archive.org/ia-pub-fts-api`` validates request
parameters strictly and reports errors in a ``user_message`` envelope, which
it sends with a 4xx status for invalid parameters and with a 200 for some
other failures (an expired scroll id, for example).
"""

import pytest
import responses

from internetarchive import search_items
from internetarchive.utils import json
from tests.conftest import PROTOCOL, IaRequestsMock

FTS_URL = f'{PROTOCOL}//be-api.us.archive.org/ia-pub-fts-api'

SCROLL_ERROR = {
    'user_message': {
        'msg_type': 'ERROR',
        'text': 'the parameter scroll must be a boolean',
    },
    'ia-pub-fts-api-wrapper': True,
}


def _page(hits, scroll_id=None):
    """Build an FTS response body holding ``hits``.

    :param hits: List of hit dicts for ``hits.hits``.
    :param scroll_id: Optional ``_scroll_id`` for the next page.
    :returns: The response body as a dict.
    """
    body = {'hits': {'total': len(hits), 'hits': hits}}
    if scroll_id is not None:
        body['_scroll_id'] = scroll_id
    return body


def _request_bodies(rsps):
    """Parse the JSON body of every request the mock received.

    :param rsps: The active ``responses`` mock.
    :returns: List of parsed request bodies, in request order.
    """
    return [json.loads(call.request.body) for call in rsps.calls]


def _collect(search, results=None):
    """Iterate ``search`` with a ``for`` loop, the way ``ia search`` does.

    ``list(search)`` would first call ``len()`` for a size hint, which sends a
    separate FTS GET for ``num_found``; these tests mock only the POSTs.

    :param search: The :class:`Search` to iterate.
    :param results: Optional list to append to, so a caller can inspect the
        results gathered before an exception.
    :returns: The list of results.
    """
    if results is None:
        results = []
    for result in search:
        results.append(result)
    return results


def test_fts_scroll_is_boolean_on_first_and_continuation(session):
    hit_a = {'fields': {'identifier': ['a']}}
    hit_b = {'fields': {'identifier': ['b']}}
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=_page([hit_a], 'scroll-1'))
        rsps.add(responses.POST, FTS_URL, json=_page([hit_b], 'scroll-2'))
        rsps.add(responses.POST, FTS_URL, json=_page([], 'scroll-3'))

        s = search_items('computer', full_text_search=True, archive_session=session)
        assert _collect(s) == [hit_a, hit_b]

        bodies = _request_bodies(rsps)
    assert len(bodies) == 3
    for body in bodies:
        assert body['scroll'] is True
    assert 'scroll_id' not in bodies[0]
    assert bodies[1]['scroll_id'] == 'scroll-1'
    assert bodies[2]['scroll_id'] == 'scroll-2'
    assert bodies[0]['q'] == '!L computer'


def test_fts_size_param_disables_scroll(session):
    hit = {'fields': {'identifier': ['a']}}
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=_page([hit], 'scroll-1'))

        s = search_items(
            'computer',
            full_text_search=True,
            params={'size': '1'},
            archive_session=session,
        )
        assert _collect(s) == [hit]

        bodies = _request_bodies(rsps)
    assert len(bodies) == 1
    assert bodies[0]['scroll'] is False
    assert bodies[0]['size'] == '1'


def test_fts_400_user_message_raises(session):
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=SCROLL_ERROR, status=400)

        s = search_items('computer', full_text_search=True, archive_session=session)
        with pytest.raises(ValueError, match='the parameter scroll must be a boolean'):
            _collect(s)


def test_fts_200_user_message_raises(session):
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=SCROLL_ERROR, status=200)

        s = search_items('computer', full_text_search=True, archive_session=session)
        with pytest.raises(ValueError, match='the parameter scroll must be a boolean'):
            _collect(s)


def test_fts_expired_scroll_id_raises_mid_scroll(session):
    # Observed live on 2026-11-05: the expired-scroll message is carried in
    # ``msg_type``, with no ``text`` key, and the status is 200.
    hit = {'fields': {'identifier': ['a']}}
    expired = {
        'user_message': {'msg_type': 'Invalid or expired scroll id'},
        'ia-pub-fts-api-wrapper': True,
    }
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=_page([hit], 'scroll-1'))
        rsps.add(responses.POST, FTS_URL, json=expired)

        s = search_items('computer', full_text_search=True, archive_session=session)
        results = []
        with pytest.raises(ValueError, match='Invalid or expired scroll id'):
            _collect(s, results)
    assert results == [hit]


def test_fts_upstream_error_envelope_raises(session):
    # Observed live on 2026-11-05 as a 504 from the FTS wrapper.
    upstream = {
        'error': 'UPSTREAM_ERROR',
        'message': (
            'The search service is temporarily unavailable, please try again later.'
        ),
        'ia-pub-fts-api-wrapper': True,
    }
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=upstream, status=504)

        s = search_items('computer', full_text_search=True, archive_session=session)
        with pytest.raises(ValueError, match='temporarily unavailable'):
            _collect(s)


def test_fts_non_json_error_raises_with_status(session):
    with IaRequestsMock() as rsps:
        rsps.add(
            responses.POST,
            FTS_URL,
            body='<html>Bad Gateway</html>',
            status=502,
            content_type='text/html',
        )

        s = search_items('computer', full_text_search=True, archive_session=session)
        with pytest.raises(ValueError, match='502'):
            _collect(s)


def test_fts_empty_result_yields_nothing(session):
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, FTS_URL, json=_page([], 'scroll-1'))

        s = search_items('computer', full_text_search=True, archive_session=session)
        assert _collect(s) == []


def test_fts_num_found_error_raises(session):
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, FTS_URL, json=SCROLL_ERROR, status=400)

        s = search_items('computer', full_text_search=True, archive_session=session)
        with pytest.raises(ValueError, match='the parameter scroll must be a boolean'):
            _ = s.num_found


def test_fts_num_found(session):
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, FTS_URL, json={'hits': {'total': 305, 'hits': []}})

        s = search_items('computer', full_text_search=True, archive_session=session)
        assert s.num_found == 305
