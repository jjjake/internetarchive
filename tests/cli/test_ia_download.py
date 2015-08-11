import os
import shutil
from subprocess import Popen, PIPE


def call(cmd):
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    return (proc.returncode, stdout, stderr)


def parse_output(output):
    return set([x for x in output[:-1].split('\n') if 'nasa:' not in x])


def rm(path):
    try:
        shutil.rmtree(path)
    except:
        try:
            os.remove(path)
        except:
            pass


def test_no_args():
    rm('nasa')

    cmd = 'ia download nasa'
    exit_code, stdout, stderr = call(cmd)
    test_output = set([
        'globe_west_540.jpg',
        'nasa_archive.torrent',
        'nasa_files.xml',
        'nasa_meta.xml',
        'nasa_reviews.xml',
        'NASAarchiveLogo.jpg',
        'globe_west_540_thumb.jpg',
    ])
    assert set(os.listdir('nasa')) == test_output
    assert exit_code == 0

    rm('nasa')


def test_dry_run():
    cmd = 'ia download --dry-run nasa'
    exit_code, stdout, stderr = call(cmd)
    test_output_set = set([
        "http://archive.org/download/nasa/NASAarchiveLogo.jpg",
        "http://archive.org/download/nasa/globe_west_540.jpg",
        "http://archive.org/download/nasa/nasa_reviews.xml",
        "http://archive.org/download/nasa/nasa_meta.xml",
        "http://archive.org/download/nasa/nasa_archive.torrent",
        "http://archive.org/download/nasa/nasa_files.xml",
        "http://archive.org/download/nasa/globe_west_540_thumb.jpg",
    ])
    assert parse_output(stdout) == test_output_set
    assert exit_code == 0


def test_glob():
    rm('nasa')

    cmd = 'ia download --glob="*jpg" nasa'
    exit_code, stdout, stderr = call(cmd)
    test_output = set([
        'globe_west_540.jpg',
        'NASAarchiveLogo.jpg',
        'globe_west_540_thumb.jpg',
    ])
    assert set(os.listdir('nasa')) == test_output
    assert exit_code == 0

    rm('nasa')


def test_source():
    rm('nasa')

    cmd = 'ia download --source=metadata nasa'
    exit_code, stdout, stderr = call(cmd)
    test_output = set([
        'nasa_archive.torrent',
        'nasa_files.xml',
        'nasa_meta.xml',
        'nasa_reviews.xml',
    ])
    assert set(os.listdir('nasa')) == test_output
    assert exit_code == 0

    rm('nasa')


def test_format():
    rm('nasa')

    cmd = 'ia download --format="Archive BitTorrent" nasa'
    exit_code, stdout, stderr = call(cmd)
    assert os.listdir('nasa') == ['nasa_archive.torrent']
    assert exit_code == 0

    rm('nasa')


def test_clobber():
    rm('nasa')

    cmd = 'ia download nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert os.listdir('nasa') == ['nasa_meta.xml']
    assert exit_code == 0

    exit_code, stdout, stderr = call(cmd)
    assert os.listdir('nasa') == ['nasa_meta.xml']
    assert ' file already downloaded: nasa/nasa_meta.xml' in parse_output(stderr)
    assert exit_code == 0

    cmd = 'ia download --clobber nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert stderr == 'nasa:\n'
    assert exit_code == 0

    rm('nasa')


def test_checksum():
    rm('nasa')

    cmd = 'ia download nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert os.listdir('nasa') == ['nasa_meta.xml']
    assert exit_code == 0

    cmd = 'ia download --checksum nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert ' skipping nasa/nasa_meta.xml: already exists.' in parse_output(stderr)
    assert exit_code == 0

    rm('nasa')


def test_no_directories():
    rm('nasa_meta.xml')

    cmd = 'ia download --no-directories nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert 'nasa_meta.xml' in os.listdir('.')
    assert exit_code == 0

    rm('nasa_meta.xml')


def test_destdir():
    rm('thisdirdoesnotexist')

    cmd = 'ia download --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert '--destdir must be a valid path to a directory.' in stderr
    assert exit_code == 1

    os.mkdir('thisdirdoesnotexist/')
    exit_code, stdout, stderr = call(cmd)
    assert 'nasa_meta.xml' in os.listdir('thisdirdoesnotexist/nasa/')
    assert exit_code == 0

    cmd = 'ia download --no-directories --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert 'nasa_meta.xml' in os.listdir('thisdirdoesnotexist/')
    assert exit_code == 0

    rm('thisdirdoesnotexist')
