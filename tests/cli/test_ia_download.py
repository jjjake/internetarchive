import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
import shutil
from subprocess import Popen, PIPE


if sys.version_info < (2, 7, 9):
    protocol = 'http:'
else:
    protocol = 'https:'


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
        '{0}//archive.org/download/nasa/NASAarchiveLogo.jpg'.format(protocol),
        '{0}//archive.org/download/nasa/globe_west_540.jpg'.format(protocol),
        '{0}//archive.org/download/nasa/nasa_reviews.xml'.format(protocol),
        '{0}//archive.org/download/nasa/nasa_meta.xml'.format(protocol),
        '{0}//archive.org/download/nasa/nasa_archive.torrent'.format(protocol),
        '{0}//archive.org/download/nasa/nasa_files.xml'.format(protocol),
        '{0}//archive.org/download/nasa/globe_west_540_thumb.jpg'.format(protocol),
    ])
    assert parse_output(stdout.decode('utf-8')) == test_output_set
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
    assert 'nasa: . - success\n' == stdout.decode('utf-8')
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
    assert 'nasa: . - success\n' == stdout.decode('utf-8')
    assert exit_code == 0

    rm('nasa')


def test_no_directories():
    rm('nasa_meta.xml')

    cmd = 'ia download --no-directories nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert 'nasa_meta.xml' in os.listdir('.')
    assert exit_code == 0

    rm('nasa_meta.xml')


def test_destdir(tmpdir):
    tmpdir.chdir()
    rm('thisdirdoesnotexist')

    cmd = 'ia download --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert '--destdir must be a valid path to a directory.' in stderr.decode('utf-8')
    assert exit_code == 1

    tmpdir.mkdir('thisdirdoesnotexist/')
    exit_code, stdout, stderr = call(cmd)
    assert 'nasa_meta.xml' in os.listdir(os.path.join(str(tmpdir),
                                         'thisdirdoesnotexist/nasa'))
    assert exit_code == 0

    cmd = 'ia download --no-directories --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    exit_code, stdout, stderr = call(cmd)
    assert 'nasa_meta.xml' in os.listdir(os.path.join(str(tmpdir),
                                         'thisdirdoesnotexist/'))
    assert exit_code == 0

    rm('thisdirdoesnotexist')
