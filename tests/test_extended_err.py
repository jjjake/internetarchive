"""Tests for ``extended_err=1`` on metadata reads and the ``Item.exists`` rule.

``GET /metadata/{identifier}?extended_err=1`` answers a never-created
identifier with ``{}`` and an identifier that exists or existed but cannot be
served with ``{"error": "<text>", "errcode": <int>}``. See
https://archive.org/developers/md-read.html, section "Extended errors".
"""

from urllib.parse import parse_qs, urlsplit

import pytest
import responses

from internetarchive import get_session
from internetarchive.utils import json
from tests.conftest import (
    PROTOCOL,
    TEST_CONFIG,
    IaRequestsMock,
    ia_call,
    load_test_data_file,
)

NASA_BODY = load_test_data_file('metadata/nasa.json')


def _query(url):
    """Return the parsed query string of a recorded request URL."""
    return parse_qs(urlsplit(url).query)


def _get_calls(rsps):
    """Return the recorded GET calls to the metadata API."""
    return [
        c
        for c in rsps.calls
        if c.request.method == 'GET' and '/metadata/' in c.request.url
    ]


# body, expected exists, expected errcode, expected error
EXISTS_CASES = [
    pytest.param('{}', False, None, None, id='empty-never-existed'),
    pytest.param(NASA_BODY, True, None, None, id='normal-item'),
    pytest.param('{"created": 1, "files": []}', True, None, None, id='no-metadata-key'),
    pytest.param(
        '{"error": "item creation pending", "errcode": 101}',
        True,
        101,
        'item creation pending',
        id='101-creation-pending',
    ),
    pytest.param(
        '{"error": "data nodes offline", "errcode": 102}',
        True,
        102,
        'data nodes offline',
        id='102-nodes-offline',
    ),
    pytest.param(
        '{"error": "unbacked user item", "errcode": 103}',
        False,
        103,
        'unbacked user item',
        id='103-unbacked',
    ),
    pytest.param(
        '{"error": "item is deleted", "errcode": 104}',
        False,
        104,
        'item is deleted',
        id='104-deleted',
    ),
    pytest.param(
        '{"error": "primary node not found", "errcode": 105}',
        True,
        105,
        'primary node not found',
        id='105-primary-not-found',
    ),
    pytest.param(
        '{"error": "secondary copy used", "errcode": 106}',
        True,
        106,
        'secondary copy used',
        id='106-secondary',
    ),
    pytest.param(
        '{"error": "inaccurate lookahead", "errcode": 400}',
        True,
        400,
        'inaccurate lookahead',
        id='400-lookahead',
    ),
    pytest.param(
        '{"error": "something went wrong"}',
        True,
        None,
        'something went wrong',
        id='error-without-errcode',
    ),
    pytest.param(
        '{"error": "item is deleted", "errcode": "104"}',
        False,
        104,
        'item is deleted',
        id='104-as-string',
    ),
]


@pytest.mark.parametrize(('body', 'exists', 'errcode', 'error'), EXISTS_CASES)
def test_item_exists_rule(body, exists, errcode, error):
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('someid', body=body)
        item = s.get_item('someid')
    assert item.exists is exists
    assert item.errcode == errcode
    assert item.error == error


def test_get_metadata_sends_extended_err():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        s.get_item('nasa')
        calls = _get_calls(rsps)
    assert len(calls) == 1
    assert _query(calls[0].request.url) == {'extended_err': ['1']}


def test_get_metadata_merges_caller_params():
    s = get_session(config_file=TEST_CONFIG)
    params = {'foo': 'bar'}
    request_kwargs = {'params': params}
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        s.get_metadata('nasa', request_kwargs)
        calls = _get_calls(rsps)
    assert _query(calls[0].request.url) == {'foo': ['bar'], 'extended_err': ['1']}
    # The caller's objects are not modified.
    assert params == {'foo': 'bar'}
    assert request_kwargs == {'params': {'foo': 'bar'}}


def test_get_metadata_merges_caller_param_pairs():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        s.get_metadata('nasa', {'params': [('foo', 'bar')]})
        calls = _get_calls(rsps)
    assert _query(calls[0].request.url) == {'foo': ['bar'], 'extended_err': ['1']}


def test_get_metadata_caller_extended_err_wins():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        s.get_metadata('nasa', {'params': {'extended_err': 0}})
        calls = _get_calls(rsps)
    assert _query(calls[0].request.url) == {'extended_err': ['0']}


def test_item_refresh_sends_extended_err():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add_metadata_mock('nasa')
        item = s.get_item('nasa')
        item.refresh()
        calls = _get_calls(rsps)
    assert len(calls) == 2
    assert all(_query(c.request.url) == {'extended_err': ['1']} for c in calls)


def test_modify_metadata_post_has_no_extended_err(session):
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        item = session.get_item('nasa')
        rsps.add(
            responses.POST,
            f'{PROTOCOL}//archive.org/metadata/nasa',
            body='{"success": true, "task_id": 1}',
        )
        item.modify_metadata({'foo': 'bar'})
        posts = [c for c in rsps.calls if c.request.method == 'POST']
    assert len(posts) == 1
    assert 'extended_err' not in posts[0].request.url


def test_reload_clears_previous_error():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock(
            'nasa', body='{"error": "data nodes offline", "errcode": 102}'
        )
        item = s.get_item('nasa')
    assert item.errcode == 102
    item.refresh(item_metadata=json.loads(NASA_BODY))
    assert item.exists is True
    assert item.errcode is None
    assert item.error is None


def test_reload_error_clears_previous_item_state():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        item = s.get_item('nasa')
    assert item.files
    assert item.metadata
    item.refresh(item_metadata={'error': 'item is deleted', 'errcode': 104})
    assert item.exists is False
    assert item.errcode == 104
    assert item.files == []
    assert item.metadata == {}
    assert list(item.get_files()) == []
    # Keys only the old response had are gone.
    assert not hasattr(item, 'workable_servers')
    assert item.identifier == 'nasa'


def test_reload_empty_clears_previous_error():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock(
            'nasa', body='{"error": "data nodes offline", "errcode": 102}'
        )
        rsps.add_metadata_mock('nasa', body='{}')
        item = s.get_item('nasa')
        assert item.exists is True
        item.refresh()
    assert item.exists is False
    assert item.errcode is None
    assert item.error is None


def test_repr():
    s = get_session(config_file=TEST_CONFIG)
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add_metadata_mock('gone', body='{}')
        rsps.add_metadata_mock(
            'deleted', body='{"error": "item is deleted", "errcode": 104}'
        )
        rsps.add_metadata_mock('oops', body='{"error": "bad"}')
        assert repr(s.get_item('nasa')) == "Collection(identifier='nasa')"
        assert repr(s.get_item('gone')) == "Item(identifier='gone', item_metadata={})"
        assert repr(s.get_item('deleted')) == (
            "Item(identifier='deleted', errcode=104, error='item is deleted')"
        )
        assert repr(s.get_item('oops')) == (
            "Item(identifier='oops', errcode=None, error='bad')"
        )


def test_ia_metadata_exists_prints_error(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock(
            'nasa', body='{"error": "item is deleted", "errcode": 104}'
        )
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=1)
        _out, err = capsys.readouterr()
    assert err == 'nasa: item is deleted (errcode 104)\nnasa does not exist\n'


def test_ia_metadata_exists_unreachable_prints_error(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock(
            'nasa', body='{"error": "data nodes offline", "errcode": 102}'
        )
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=0)
        _out, err = capsys.readouterr()
    assert err == 'nasa: data nodes offline (errcode 102)\nnasa exists\n'


def test_ia_metadata_exists_empty_error_text(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', body='{"error": "", "errcode": 104}')
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=1)
        _out, err = capsys.readouterr()
    assert err == 'nasa: (errcode 104)\nnasa does not exist\n'


def test_ia_metadata_exists_error_without_errcode(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', body='{"error": "bad"}')
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=0)
        _out, err = capsys.readouterr()
    assert err == 'nasa: bad\nnasa exists\n'
