import os, sys
from subprocess import Popen, PIPE
from time import time

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config


pytestmark = pytest.mark.skipif('internetarchive.config.get_config().get("s3") is None',
                                reason='requires authorization.')

def test_ia_upload_from_stdin():
    cmd = ('echo "Hello World!" |'
           'ia upload iacli-test-item - --remote-name="stdin.txt" --size-hint=8')
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, stderr

    cmd = ('echo "Hello World!" |'
           'ia upload iacli-test-item -')
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 1
    assert stderr == '--remote-name is required when uploading from stdin.\n'

def test_ia_upload_file():
    cmd = 'ia upload iacli-test-item setup.py'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, stderr

def test_ia_upload_debug():
    cmd = 'ia upload iacli-test-item setup.py --debug'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, stderr

def test_ia_upload_bad_request():
    # upload non-200 status_code.
    cmd = ('echo "Hello World!" |'
           'ia upload iacli-test-item - --remote-name="iacli-test-item_meta.xml"')
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert stderr == 'error "AccessDenied" (403): Access Denied\n'
    assert proc.returncode == 1
