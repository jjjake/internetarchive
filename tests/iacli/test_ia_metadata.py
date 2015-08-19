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
    cmd = 'ia metadata --formats iacli-test-item60'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output_set = set([
        'Text',
        'Metadata',
        'Unknown',
    ])
    assert set(stdout[:-1].split('\n')) == test_output_set

@pytest.mark.skipif('internetarchive.config.get_config().get("cookies") == None',
                    reason='requires authorization.')
def test_ia_metadata_modify():
    # Modify test item.
    valid_key = "foo-{k}".format(k=int(time())) 
    cmd = 'ia metadata --modify="{k}:test_value" iacli-test-item60'.format(k=valid_key)
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    # Submit illegal modification.
    cmd = 'ia metadata --modify="-foo:test_value" iacli-test-item60'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 1
    assert "Illegal tag name" in stderr
