import sys
from time import time

import responses

from internetarchive.cli import ia
from tests.conftest import IaRequestsMock


def test_ia_metadata_exists(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        sys.argv = ['ia', 'metadata', '--exists', 'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 0
        out, err = capsys.readouterr()
        assert out == 'nasa exists\n'
        rsps.add_metadata_mock('nasa', '{}')
        sys.argv = ['ia', 'metadata', '--exists', 'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 1
        out, err = capsys.readouterr()
        assert err == 'nasa does not exist\n'


def test_ia_metadata_formats(capsys, nasa_mocker):
    sys.argv = ['ia', 'metadata', '--formats', 'nasa']
    try:
        ia.main()
    except SystemExit as exc:
        assert exc.code == 0
    out, err = capsys.readouterr()
    assert set(out.split('\n')) == set(['Collection Header', 'Archive BitTorrent',
                                        'JPEG', 'Metadata', ''])


def test_ia_metadata_modify(capsys):
    md_rsp = ('{"success":true,"task_id":447613301,'
              '"log":"https://catalogd.archive.org/log/447613301"}')
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add_metadata_mock('nasa', body=md_rsp, method=responses.POST)
        rsps.add_metadata_mock('nasa')
        valid_key = "foo-{k}".format(k=int(time()))
        sys.argv = ['ia', 'metadata', '--modify', '{0}:test_value'.format(valid_key),
                    'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 0
        out, err = capsys.readouterr()
        assert out == 'nasa - success: https://catalogd.archive.org/log/447613301\n'
