import os, sys, shutil
from subprocess import Popen, PIPE
from time import time

import pytest

inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import internetarchive.config



def test_ia_download():
    cmd = 'ia download --dry-run nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output_set = set([
        "http://archive.org/download/nasa/NASAarchiveLogo.jpg",
        "http://archive.org/download/nasa/globe_west_540.jpg",
        "http://archive.org/download/nasa/nasa_reviews.xml",
        "http://archive.org/download/nasa/nasa_meta.xml",
        "http://archive.org/download/nasa/nasa_archive.torrent",
        "http://archive.org/download/nasa/nasa_files.xml",
        "http://archive.org/download/nasa/globe_west_540_thumb.jpg",
    ])
    output = set([x for x in stdout[:-1].split('\n') if 'nasa:' not in x])  
    assert output == test_output_set

    cmd = 'ia download --ignore-existing nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output = [
        'globe_west_540.jpg', 
        'nasa_archive.torrent', 
        'nasa_files.xml', 
        'nasa_meta.xml', 
        'nasa_reviews.xml', 
        'NASAarchiveLogo.jpg',
        'globe_west_540_thumb.jpg',
    ]
    assert sorted(os.listdir('nasa')) == sorted(test_output)
    shutil.rmtree('nasa')

    cmd = 'ia download --ignore-existing --glob="*jpg" nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output = [
        'globe_west_540.jpg', 
        'NASAarchiveLogo.jpg',
        'globe_west_540_thumb.jpg',
    ]
    assert sorted(os.listdir('nasa')) == sorted(test_output)
    shutil.rmtree('nasa')

    cmd = 'ia download --ignore-existing --source=metadata nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output = [
        'nasa_archive.torrent', 
        'nasa_files.xml', 
        'nasa_meta.xml', 
        'nasa_reviews.xml', 
    ]
    assert sorted(os.listdir('nasa')) == sorted(test_output)
    shutil.rmtree('nasa')

    cmd = 'ia download --ignore-existing --format="Archive BitTorrent" nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output = [
        'nasa_archive.torrent', 
    ]
    assert sorted(os.listdir('nasa')) == sorted(test_output)
    shutil.rmtree('nasa')

    cmd = 'ia download nasa nasa_meta.xml'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    assert proc.returncode == 0
    shutil.rmtree('nasa')
