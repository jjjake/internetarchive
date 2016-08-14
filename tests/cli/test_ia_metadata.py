import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
from time import time

import responses

from internetarchive.cli import ia


protocol = 'https:'


def test_ia_metadata_exists(capsys, testitem_metadata):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=testitem_metadata,
                 status=200)
        sys.argv = ['ia', 'metadata', '--exists', 'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 0
        out, err = capsys.readouterr()
        assert out == 'nasa exists\n'

        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body='{}',
                 status=200)
        sys.argv = ['ia', 'metadata', '--exists', 'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 1
        out, err = capsys.readouterr()
        assert err == 'nasa does not exist\n'


def test_ia_metadata_formats(capsys, testitem_metadata):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=testitem_metadata,
                 status=200)
        sys.argv = ['ia', 'metadata', '--formats', 'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 0
        out, err = capsys.readouterr()
        assert set(out.split('\n')) == set(['Collection Header', 'Archive BitTorrent',
                                            'JPEG', 'Metadata', ''])


def test_ia_metadata_modify(capsys, testitem_metadata):
    md_rsp = ('{"success":true,"task_id":447613301,'
              '"log":"https://catalogd.archive.org/log/447613301"}')
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=testitem_metadata,
                 status=200)
        rsps.add(responses.POST, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=md_rsp,
                 status=200)
        rsps.add(responses.GET, '{0}//archive.org/metadata/nasa'.format(protocol),
                 body=testitem_metadata,
                 status=200)
        valid_key = "foo-{k}".format(k=int(time()))
        sys.argv = ['ia', 'metadata', '--modify', '{0}:test_value'.format(valid_key),
                    'nasa']
        try:
            ia.main()
        except SystemExit as exc:
            assert exc.code == 0
        out, err = capsys.readouterr()
        assert out == 'nasa - success: https://catalogd.archive.org/log/447613301\n'
