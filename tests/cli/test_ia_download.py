import os
import sys
import time

import pytest

from tests.conftest import NASA_EXPECTED_FILES, call_cmd, files_downloaded


def test_no_args(tmpdir_ch):
    call_cmd('ia --insecure download nasa')
    assert files_downloaded(path='nasa') == NASA_EXPECTED_FILES


@pytest.mark.xfail("CI" in os.environ, reason="May timeout on continuous integration")
def test_https(tmpdir_ch):
    call_cmd('ia download nasa')
    assert files_downloaded(path='nasa') == NASA_EXPECTED_FILES


def test_dry_run():
    nasa_url = 'http://archive.org/download/nasa/'
    expected_urls = {nasa_url + f for f in NASA_EXPECTED_FILES}

    stdout, stderr = call_cmd('ia --insecure download --dry-run nasa')
    output_lines = stdout.split('\n')
    dry_run_urls = {x.strip() for x in output_lines if x and 'nasa:' not in x}

    assert expected_urls == dry_run_urls


def test_glob(tmpdir_ch):
    expected_files = {
        'globe_west_540.jpg',
        'globe_west_540_thumb.jpg',
        'nasa_itemimage.jpg',
        '__ia_thumb.jpg',
    }

    call_cmd('ia --insecure download --glob="*jpg" nasa')
    assert files_downloaded(path='nasa') == expected_files


def test_exclude(tmpdir_ch):
    expected_files = {
        'globe_west_540.jpg',
        'nasa_itemimage.jpg',
    }

    call_cmd('ia --insecure download --glob="*jpg" --exclude="*thumb*" nasa')
    assert files_downloaded(path='nasa') == expected_files


def test_format(tmpdir_ch):
    call_cmd('ia --insecure download --format="Archive BitTorrent" nasa')
    assert files_downloaded(path='nasa') == {'nasa_archive.torrent'}


def test_on_the_fly_format():
    i = 'wonderfulwizardo00baumiala'

    stdout, stderr = call_cmd(f'ia --insecure download --dry-run --format="DAISY" {i}')
    assert stdout == ''

    stdout, stderr = call_cmd(f'ia --insecure download --dry-run --format="DAISY" --on-the-fly {i}')
    assert stdout == f'http://archive.org/download/{i}/{i}_daisy.zip'


def test_clobber(tmpdir_ch):
    cmd = 'ia --insecure download nasa nasa_meta.xml'
    call_cmd(cmd)
    assert files_downloaded('nasa') == {'nasa_meta.xml'}

    stdout, stderr = call_cmd(cmd)
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    expected_stderr = f'{prefix} skipping {filepath}, file already exists based on length and date.'
    assert expected_stderr == stderr


def test_checksum(tmpdir_ch):
    call_cmd('ia --insecure download nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}

    stdout, stderr = call_cmd('ia --insecure download --checksum nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    assert f'{prefix} skipping {filepath}, file already exists based on checksum.' == stderr


def test_checksum_archive(tmpdir_ch):
    call_cmd('ia --insecure download nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}

    stdout, stderr = call_cmd('ia --insecure download --checksum-archive nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    assert f'{prefix} skipping {filepath}, file already exists based on checksum.' == stderr

    assert '_checksum_archive.txt' in files_downloaded('.')
    with open(os.path.join('.', '_checksum_archive.txt'), encoding='utf-8') as f:
        filepath = os.path.join('nasa', 'nasa_meta.xml')
        assert f.read() == f'{filepath}\n'

    stdout, stderr = call_cmd('ia --insecure download --checksum-archive nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    assert f'{prefix} skipping {filepath}, file already exists based on checksum_archive.' == stderr


def test_no_directories(tmpdir_ch):
    call_cmd('ia --insecure download --no-directories nasa nasa_meta.xml')
    assert files_downloaded('.') == {'nasa_meta.xml'}


def test_destdir(tmpdir_ch):
    cmd = 'ia --insecure download --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    stdout, stderr = call_cmd(cmd, expected_exit_code=2)

    assert "--destdir: 'thisdirdoesnotexist/' is not a valid directory" in stderr

    tmpdir_ch.mkdir('thisdirdoesnotexist/')
    call_cmd(cmd)
    assert files_downloaded('thisdirdoesnotexist/nasa') == {'nasa_meta.xml'}

    tmpdir_ch.mkdir('dir2/')
    cmd = ('ia --insecure download --no-directories --destdir=dir2/ '
           'nasa nasa_meta.xml')
    call_cmd(cmd)
    assert files_downloaded('dir2') == {'nasa_meta.xml'}


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
