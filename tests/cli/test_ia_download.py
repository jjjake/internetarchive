import sys
import os
import time

from tests.conftest import call_cmd, NASA_EXPECTED_FILES, files_downloaded


def test_no_args(tmpdir_ch):
    call_cmd('ia --insecure download nasa')
    assert files_downloaded(path='nasa') == NASA_EXPECTED_FILES


def test_https(tmpdir_ch):
    if sys.version_info < (2, 7, 9):
        stdout, stderr = call_cmd('ia download nasa', expected_exit_code=1)
        assert 'You are attempting to make an HTTPS' in stderr
    else:
        call_cmd('ia download nasa')
        assert files_downloaded(path='nasa') == NASA_EXPECTED_FILES


def test_dry_run():
    nasa_url = 'http://archive.org/download/nasa/'
    expected_urls = set([nasa_url + f for f in NASA_EXPECTED_FILES])

    stdout, stderr = call_cmd('ia --insecure download --dry-run nasa')
    output_lines = stdout.split('\n')
    dry_run_urls = set([x.strip() for x in output_lines if x and 'nasa:' not in x])

    assert expected_urls == dry_run_urls


def test_glob(tmpdir_ch):
    expected_files = set([
        'globe_west_540.jpg',
        'globe_west_540_thumb.jpg',
        'nasa_itemimage.jpg',
        '__ia_thumb.jpg',
    ])

    call_cmd('ia --insecure download --glob="*jpg" nasa')
    assert files_downloaded(path='nasa') == expected_files


def test_format(tmpdir_ch):
    call_cmd('ia --insecure download --format="Archive BitTorrent" nasa')
    assert files_downloaded(path='nasa') == set(['nasa_archive.torrent'])


def test_clobber(tmpdir_ch):
    cmd = 'ia --insecure download nasa nasa_meta.xml'
    call_cmd(cmd)
    assert files_downloaded('nasa') == set(['nasa_meta.xml'])

    stdout, stderr = call_cmd(cmd)
    assert files_downloaded('nasa') == set(['nasa_meta.xml'])
    assert 'nasa: . - success' == stdout


def test_checksum(tmpdir_ch):
    call_cmd('ia --insecure download nasa nasa_meta.xml')
    assert files_downloaded('nasa') == set(['nasa_meta.xml'])

    stdout, stderr = call_cmd('ia --insecure download --checksum nasa nasa_meta.xml')
    assert files_downloaded('nasa') == set(['nasa_meta.xml'])

    assert 'nasa: . - success' == stdout


def test_no_directories(tmpdir_ch):
    call_cmd('ia --insecure download --no-directories nasa nasa_meta.xml')
    assert files_downloaded('.') == set(['nasa_meta.xml'])


def test_destdir(tmpdir_ch):
    cmd = 'ia --insecure download --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    stdout, stderr = call_cmd(cmd, expected_exit_code=1)

    assert '--destdir must be a valid path to a directory.' in stderr

    tmpdir_ch.mkdir('thisdirdoesnotexist/')
    call_cmd(cmd)
    assert files_downloaded('thisdirdoesnotexist/nasa') == set(['nasa_meta.xml'])

    tmpdir_ch.mkdir('dir2/')
    cmd = ('ia --insecure download --no-directories --destdir=dir2/ '
           'nasa nasa_meta.xml')
    call_cmd(cmd)
    assert files_downloaded('dir2') == set(['nasa_meta.xml'])


def test_no_change_timestamp(tmpdir_ch):
    # TODO: Handle the case of daylight savings time

    now = time.time()
    call_cmd('ia --insecure download --no-change-timestamp nasa')

    for path, dirnames, filenames in os.walk(str(tmpdir_ch)):
        for d in dirnames:
            p = os.path.join(path, d)
            assert os.stat(p).st_mtime >= now

        for f in filenames:
            p = os.path.join(path, f)
            assert os.stat(p).st_mtime >= now
