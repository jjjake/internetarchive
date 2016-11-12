import os
import sys
import tempfile

from tests.conftest import call_cmd

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError

try:
    WindowsError
except NameError:
    class WindowsError(Exception):
        pass


def assert_cmd_call_downloads_files(cmd, expected_files, destdir, tmpdir=None,
                                    expected_exit_code=0):
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    os.chdir(str(tmpdir))
    exit_code, stdout, stderr = call_cmd(cmd)
    found_files = set([])
    try:
        found_files = set(os.listdir(destdir))
    except (FileNotFoundError, WindowsError, OSError):
        pass

    assert found_files == expected_files
    assert expected_exit_code == exit_code
    return exit_code, stdout, stderr


def test_no_args():
    assert_cmd_call_downloads_files(
        cmd='ia --insecure download nasa',
        expected_files=set([
            'globe_west_540.jpg',
            'nasa_archive.torrent',
            'nasa_files.xml',
            'nasa_meta.xml',
            'nasa_reviews.xml',
            'NASAarchiveLogo.jpg',
            'globe_west_540_thumb.jpg',
        ]),
        destdir='nasa'
    )


def test_https(tmpdir):
    cmd = 'ia download nasa'

    if sys.version_info < (2, 7, 9):
        tmpdir.chdir()
        exit_code, stdout, stderr = call_cmd(cmd)
        assert exit_code == 1
        assert 'You are attempting to make an HTTPS' in stderr
    else:
        assert_cmd_call_downloads_files(
            cmd=cmd,
            expected_files=set([
                'globe_west_540.jpg',
                'nasa_archive.torrent',
                'nasa_files.xml',
                'nasa_meta.xml',
                'nasa_reviews.xml',
                'NASAarchiveLogo.jpg',
                'globe_west_540_thumb.jpg',
            ]),
            destdir='nasa'
        )


def test_dry_run():
    nasa_url = 'http://archive.org/download/nasa/'
    expected_set = set([
        '{0}NASAarchiveLogo.jpg'.format(nasa_url),
        '{0}globe_west_540.jpg'.format(nasa_url),
        '{0}nasa_reviews.xml'.format(nasa_url),
        '{0}nasa_meta.xml'.format(nasa_url),
        '{0}nasa_archive.torrent'.format(nasa_url),
        '{0}nasa_files.xml'.format(nasa_url),
        '{0}globe_west_540_thumb.jpg'.format(nasa_url),
    ])

    exit_code, stdout, stderr = assert_cmd_call_downloads_files(
        cmd='ia --insecure download --dry-run nasa',
        expected_files=set([]),
        destdir='nasa'
    )

    output_lines = stdout.decode('utf-8')[:-1].split('\n')
    output_set = set([x.strip() for x in output_lines if 'nasa:' not in x])
    assert output_set == expected_set


def test_glob():
    assert_cmd_call_downloads_files(
        cmd='ia --insecure download --glob="*jpg" nasa',
        expected_files=set([
            'globe_west_540.jpg',
            'NASAarchiveLogo.jpg',
            'globe_west_540_thumb.jpg',
        ]),
        destdir='nasa'
    )


def test_format():
    assert_cmd_call_downloads_files(
        cmd='ia --insecure download --format="Archive BitTorrent" nasa',
        expected_files=set(['nasa_archive.torrent']),
        destdir='nasa'
    )


def test_clobber(tmpdir):
    cmd = 'ia --insecure download nasa nasa_meta.xml'
    assert_cmd_call_downloads_files(
        cmd=cmd,
        expected_files=set(['nasa_meta.xml']),
        destdir='nasa',
        tmpdir=tmpdir
    )

    exit_code, stdout, stderr = assert_cmd_call_downloads_files(
        cmd=cmd,
        expected_files=set(['nasa_meta.xml']),
        destdir='nasa',
        tmpdir=tmpdir
    )
    assert 'nasa: . - success' == stdout.decode('utf-8').strip()


def test_checksum(tmpdir):
    assert_cmd_call_downloads_files(
        cmd='ia --insecure download nasa nasa_meta.xml',
        expected_files=set(['nasa_meta.xml']),
        destdir='nasa',
        tmpdir=tmpdir
    )

    exit_code, stdout, stderr = assert_cmd_call_downloads_files(
        cmd='ia --insecure download --checksum nasa nasa_meta.xml',
        expected_files=set(['nasa_meta.xml']),
        destdir='nasa',
        tmpdir=tmpdir
    )
    assert 'nasa: . - success' == stdout.decode('utf-8').strip()


def test_no_directories():
    assert_cmd_call_downloads_files(
        cmd='ia --insecure download --no-directories nasa nasa_meta.xml',
        expected_files=set(['nasa_meta.xml']),
        destdir='.'
    )


def test_destdir(tmpdir):
    cmd = 'ia --insecure download --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    exit_code, stdout, stderr = assert_cmd_call_downloads_files(
        cmd=cmd,
        expected_files=set(),
        destdir='thisdirdoesnotexist/nasa',
        tmpdir=tmpdir,
        expected_exit_code=1
    )
    assert '--destdir must be a valid path to a directory.' in stderr.decode('utf-8')

    tmpdir.mkdir('thisdirdoesnotexist/')
    assert_cmd_call_downloads_files(
        cmd=cmd,
        expected_files=set(['nasa_meta.xml']),
        destdir='thisdirdoesnotexist/nasa',
        tmpdir=tmpdir,
    )

    tmpdir.mkdir('dir2/')
    cmd = ('ia --insecure download --no-directories --destdir=dir2/ '
           'nasa nasa_meta.xml')
    assert_cmd_call_downloads_files(
        cmd=cmd,
        expected_files=set(['nasa_meta.xml']),
        destdir='dir2',
        tmpdir=tmpdir,
    )
