import os, sys
from subprocess import Popen, PIPE
from time import time

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config


def test_ia_list():
    nasa_files = ['NASAarchiveLogo.jpg', 'globe_west_540.jpg', 'nasa_reviews.xml',
                  'nasa_meta.xml', 'nasa_archive.torrent', 'nasa_files.xml']
    cmd = 'ia ls nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    output = [x.strip() for x in stdout.split('\n')]
    assert all(f in output  for f in nasa_files)
    assert proc.returncode == 0, stderr

def test_ia_list_glob():
    cmd = 'ia ls nasa --glob="*torrent"'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert stdout == 'nasa_archive.torrent\r\n'
    assert proc.returncode == 0, stderr

def test_ia_list_verbose():
    cmd = 'ia ls nasa --all --verbose'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, stderr

def test_ia_list_location():
    cmd = 'ia ls nasa --location'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0, stderr
