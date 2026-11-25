import json

import pytest
import responses

from tests.conftest import IaRequestsMock, ia_call

XAUTHN_URL = 'https://archive.org/services/xauthn/'

ACCOUNT_VALUES = {
    'canonical_email': 'foo@example.com',
    'email': 'foo@example.com',
    'has_disability_access': False,
    'itemname': '@foo',
    'locked': False,
    'notifications': [],
    'screenname': 'foo',
    'verified': True,
    'lastlogin': '2026-01-01 00:00:00',
    'createdate': '2020-01-01 00:00:00',
}


def test_ia_account_lookup(capsys):
    with IaRequestsMock() as rsps:
        rsps.add(
            responses.POST,
            XAUTHN_URL,
            json={'success': True, 'values': ACCOUNT_VALUES},
        )
        ia_call(['ia', 'account', 'foo'])
        assert rsps.calls[0].request.url == f'{XAUTHN_URL}?op=info'
        assert rsps.calls[0].request.body == 'screenname=foo'
    out, _err = capsys.readouterr()
    assert json.loads(out) == ACCOUNT_VALUES


@pytest.mark.parametrize(
    ('email', 'body'),
    [
        ('foo@example.com', 'email=foo%40example.com'),
        ('foo@example.co.uk', 'email=foo%40example.co.uk'),
        ('foo@mail.example.org', 'email=foo%40mail.example.org'),
    ],
)
def test_ia_account_lookup_by_email(capsys, email, body):
    with IaRequestsMock() as rsps:
        rsps.add(
            responses.POST,
            XAUTHN_URL,
            json={'success': True, 'values': ACCOUNT_VALUES},
        )
        ia_call(['ia', 'account', email])
        assert rsps.calls[0].request.body == body


def test_ia_account_api_error_prints_response(capsys):
    error_body = {'success': False, 'error': 'account not found', 'values': {}}
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, XAUTHN_URL, json=error_body)
        ia_call(['ia', 'account', 'nobody'], expected_exit_code=1)
    out, err = capsys.readouterr()
    assert json.loads(out) == error_body
    assert err == ''


def test_ia_account_request_error_prints_message(capsys):
    # The endpoint answers some requests with an HTTP 400 and a generic HTML
    # page: no JSON body, so the CLI must report the failure rather than
    # printing "null".
    with IaRequestsMock() as rsps:
        rsps.add(responses.POST, XAUTHN_URL, status=400, body='<html></html>')
        ia_call(['ia', 'account', 'nobody'], expected_exit_code=1)
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith('error: Failed to fetch account data: 400')
