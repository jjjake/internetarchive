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
    test_output = '\n'.join([
        "http://archive.org/download/nasa/NASAarchiveLogo.jpg",
        "http://archive.org/download/nasa/globe_west_540.jpg",
        "http://archive.org/download/nasa/nasa_reviews.xml",
        "http://archive.org/download/nasa/nasa_meta.xml",
        "http://archive.org/download/nasa/nasa_archive.torrent",
        "http://archive.org/download/nasa/nasa_files.xml\n",
    ])
    assert stdout == test_output

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
    ]
    assert sorted(os.listdir('nasa')) == sorted(test_output)
    shutil.rmtree('nasa')

    cmd = 'ia download --ignore-existing --glob="*jpg" nasa'
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    test_output = [
        'globe_west_540.jpg', 
        'NASAarchiveLogo.jpg',
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
