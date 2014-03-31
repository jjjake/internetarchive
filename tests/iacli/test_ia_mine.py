import os, sys
from subprocess import Popen, PIPE
from time import time
import tempfile

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config

@pytest.fixture
def dir_with_testlist():
    newpath = tempfile.mkdtemp()
    os.chdir(newpath)
    with open('testlist.txt', 'w') as fp:
        fp.write('\n'.join(['nasa', 'iacli-test-item']))


@pytest.mark.usefixtures('dir_with_testlist')
class TestMineWithTestlist:
    def test_ia_mine_cache(self):
        cmd = 'ia mine testlist.txt --cache'
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        assert proc.returncode == 0
        
    def test_ia_mine_output(self):
        cmd = 'ia mine testlist.txt --output=d.json'
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        assert proc.returncode == 0
        
    def test_ia_mine_plain(self):
        cmd = 'ia mine testlist.txt'
        proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        assert proc.returncode == 0
        
        
def test_ia_mine_stdin():
    cmd = 'echo "nasa" | ia mine -'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0
