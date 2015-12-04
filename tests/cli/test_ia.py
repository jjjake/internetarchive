import os, sys
from subprocess import Popen, PIPE
import subprocess
from time import time
from copy import deepcopy

import pytest
import responses

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config
from internetarchive.cli import ia
from internetarchive import get_session


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')
SESSION = get_session()
with open(TEST_JSON_FILE, 'r') as fh:
    ITEM_METADATA = fh.read().strip().decode('utf-8')


def test_ia(capsys):
    sys.argv = ['ia', '--help']
    try:
        ia.main()
    except SystemExit as exc:
        assert not exc.code
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in out

    try:
        sys.argv = ['ia', 'ls', 'nasa']
        ia.main()
    except SystemExit as exc:
        assert not exc.code

    try:
        sys.argv = ['ia', 'nocmd']
        ia.main()
    except SystemExit as exc:
        assert exc.code == 127
    out, err = capsys.readouterr()
    assert "error: 'nocmd' is not an ia command!" in err

    try:
        sys.argv = ['ia', 'help']
        ia.main()
    except SystemExit as exc:
        assert not exc.code
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in err

    try:
        sys.argv = ['ia', 'help', 'list']
        ia.main()
    except SystemExit as exc:
        assert not exc.code


def ia_list(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'http://archive.org/metadata/nasa',
                 body=ITEM_METADATA,
                 status=200)

        ia_list.main(['list', 'nasa'], SESSION)

    out, err = capsys.readouterr()
    assert set([l for l in out.split('\n') if l]) == NASA_FILES
