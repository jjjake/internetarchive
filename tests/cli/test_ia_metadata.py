import sys
from time import time

import responses

from tests.conftest import IaRequestsMock, ia_call


def test_ia_metadata_exists(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=0)
        out, err = capsys.readouterr()
        assert out == 'nasa exists\n'
        rsps.reset()
        rsps.add_metadata_mock('nasa', '{}')
        sys.argv = ['ia', 'metadata', '--exists', 'nasa']
        ia_call(['ia', 'metadata', '--exists', 'nasa'], expected_exit_code=1)
        out, err = capsys.readouterr()
        assert err == 'nasa does not exist\n'


def test_ia_metadata_formats(capsys, nasa_mocker):
    ia_call(['ia', 'metadata', '--formats', 'nasa'])
    out, err = capsys.readouterr()
    expected_formats = set(['Collection Header', 'Archive BitTorrent', 'JPEG',
                            'Metadata', ''])
    assert set(out.split('\n')) == expected_formats


def test_ia_metadata_modify(capsys):
    md_rsp = ('{"success":true,"task_id":447613301,'
              '"log":"https://catalogd.archive.org/log/447613301"}')
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add_metadata_mock('nasa', body=md_rsp, method=responses.POST)
        rsps.add_metadata_mock('nasa')
        valid_key = "foo-{k}".format(k=int(time()))
        ia_call(['ia', 'metadata', '--modify', '{0}:test_value'.format(valid_key),
                 'nasa'])
        out, err = capsys.readouterr()
        assert out == 'nasa - success: https://catalogd.archive.org/log/447613301\n'
