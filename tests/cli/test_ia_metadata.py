import sys
from time import time

import responses

from tests.conftest import IaRequestsMock, ia_call


def test_ia_metadata_exists(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=0)
        _out, err = capsys.readouterr()
        assert err == 'nasa exists\n'
        rsps.reset()
        rsps.add_metadata_mock('nasa', '{}')
        sys.argv = ['ia', 'metadata', '--exists', 'nasa']
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=1)
        _out, err = capsys.readouterr()
        assert err == 'nasa does not exist\n'


def test_ia_metadata_formats(capsys, nasa_mocker):
    ia_call(['ia', 'metadata', '--formats', 'nasa'])
    out, _err = capsys.readouterr()
    expected_formats = {'Collection Header', 'Archive BitTorrent', 'JPEG',
                        'Metadata', ''}
    assert set(out.split('\n')) == expected_formats


def test_ia_metadata_modify(capsys):
    md_rsp = ('{"success":true,"task_id":447613301,'
              '"log":"https://catalogd.archive.org/log/447613301"}')
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', method=responses.GET)
        rsps.add_metadata_mock('nasa', body=md_rsp, method=responses.POST)
        valid_key = f'foo-{int(time())}'
        ia_call(['ia', 'metadata', 'nasa', '--modify', f'{valid_key}:test_value'])
        _out, err = capsys.readouterr()
        assert err == 'nasa - success: https://catalogd.archive.org/log/447613301\n'
