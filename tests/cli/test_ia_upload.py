import os
import sys
from subprocess import Popen, PIPE

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config


@pytest.mark.skipif('internetarchive.config.get_config().get("s3") is None',
                    reason='requires authorization.')
def test_ia_upload():
    # upload from stdin.
    cmd = ('echo "Hello World!" |'
           'ia upload iacli-test-item60 - --remote-name="stdin.txt" --size-hint=8')
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    cmd = ('echo "Hello World!" |'
           'ia upload iacli-test-item60 -')
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert stderr.split('\n')[0] == '--remote-name must be provided when uploading from stdin.'

    # upload file.
    cmd = 'ia upload iacli-test-item60 setup.py'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    # upload debug.
    cmd = 'ia upload iacli-test-item60 setup.py --debug'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0

    # upload non-200 status_code.
    cmd = ('echo "Hello World!" |'
           'ia upload -q iacli-test-item60 - --remote-name="iacli-test-item60_meta.xml"')
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 1
    assert stderr == ' * error uploading iacli-test-item60_meta.xml (403): Access Denied\n'
