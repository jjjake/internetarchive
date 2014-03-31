import os, sys
from subprocess import Popen, PIPE
from time import time

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config


def test_ia_metadata_exists():
    cmd = 'ia metadata --exists iacli_test-doesnotexist'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 1

    cmd = 'ia metadata --exists nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

def test_ia_metadata_formats():
    cmd = 'ia metadata --formats iacli_test_item'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output = '\n'.join([
        "Text",
        "Archive BitTorrent",
        "Metadata\n",
    ])
    assert stdout == test_output

@pytest.mark.skipif('internetarchive.config.get_config().get("cookies") == None',
                    reason='requires authorization.')
class TestIaMetadataModify:
    def test_modify_test_item():
        valid_key = "foo-{k}".format(k=int(time())) 
        cmd = 'ia metadata --modify="{k}:test_value" iacli_test_item'.format(k=valid_key)
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        assert proc.returncode == 0

    def test_submit_illegal_modification():
        cmd = 'ia metadata --modify="-foo:test_value" iacli_test_item'
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        assert proc.returncode == 1
        assert stderr == "error: Illegal tag name '-foo' (400)\n"
