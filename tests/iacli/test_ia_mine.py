import os, sys
from subprocess import Popen, PIPE
from time import time

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config


def test_ia_mine():
    with open('testlist.txt', 'w') as fp:
        fp.write('\n'.join(['nasa', 'iacli-test-item']))

    cmd = 'ia mine testlist.txt --cache'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    cmd = 'ia mine testlist.txt --output=d.json'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    cmd = 'ia mine testlist.txt'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    # Test ids from stdin.
    cmd = 'echo "nasa" | ia mine -'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    os.remove('testlist.txt')
    os.remove('d.json')
    os.remove('nasa_meta.json')
    os.remove('iacli-test-item_meta.json')

