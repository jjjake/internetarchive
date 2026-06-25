import argparse
import os
import re
import sys
import time

import pytest
import responses

from internetarchive import get_item
from internetarchive.cli.ia_download import (
    build_range_jobs,
    normalize_byte_range,
    parse_byte_ranges,
)
from internetarchive.utils import json
from tests.conftest import (
    NASA_EXPECTED_FILES,
    IaRequestsMock,
    call_cmd,
    files_downloaded,
    ia_call,
    load_test_data_file,
)


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

    stdout, _stderr = call_cmd('ia --insecure download --dry-run nasa')
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


def _dry_run_filenames(capsys):
    out, _err = capsys.readouterr()
    return {line.split('/')[-1] for line in out.split('\n') if line and 'nasa:' not in line}


def test_glob_repeated(tmpdir_ch, capsys):
    """`--glob` repeated multiple times should union the patterns."""
    with IaRequestsMock() as mocker:
        mocker.add_metadata_mock('nasa')
        ia_call(['ia', '--insecure', 'download', '--dry-run',
                 '--glob', '*meta.xml', '--glob', '*reviews.xml', 'nasa'])
    assert _dry_run_filenames(capsys) == {'nasa_meta.xml', 'nasa_reviews.xml'}


def test_glob_mixed_pipe_and_repeated(tmpdir_ch, capsys):
    """`--glob "a|b" --glob c` should match the union of all three patterns."""
    with IaRequestsMock() as mocker:
        mocker.add_metadata_mock('nasa')
        ia_call(['ia', '--insecure', 'download', '--dry-run',
                 '--glob', '*meta.xml|*reviews.xml', '--glob', '*.torrent', 'nasa'])
    assert _dry_run_filenames(capsys) == {
        'nasa_meta.xml', 'nasa_reviews.xml', 'nasa_archive.torrent',
    }


def test_exclude_repeated(tmpdir_ch, capsys):
    """`--exclude` repeated multiple times should union the excludes."""
    with IaRequestsMock() as mocker:
        mocker.add_metadata_mock('nasa')
        ia_call(['ia', '--insecure', 'download', '--dry-run',
                 '--glob', '*.xml',
                 '--exclude', '*reviews*', '--exclude', '*files*',
                 'nasa'])
    assert _dry_run_filenames(capsys) == {'nasa_meta.xml'}


def test_format(tmpdir_ch):
    call_cmd('ia --insecure download --format="Archive BitTorrent" nasa')
    assert files_downloaded(path='nasa') == {'nasa_archive.torrent'}


def test_on_the_fly_format():
    i = 'wonderfulwizardo00baumiala'

    stdout, _stderr = call_cmd(f'ia --insecure download --dry-run --format="DAISY" {i}')
    assert stdout == ''

    stdout, _stderr = call_cmd(f'ia --insecure download --dry-run --format="DAISY" --on-the-fly {i}')
    assert stdout == f'http://archive.org/download/{i}/{i}_daisy.zip'


def test_clobber(tmpdir_ch):
    cmd = 'ia --insecure download nasa nasa_meta.xml'
    call_cmd(cmd)
    assert files_downloaded('nasa') == {'nasa_meta.xml'}

    _stdout, stderr = call_cmd(cmd)
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    expected_stderr = f'{prefix} skipping {filepath}, file already exists based on length and date.'
    assert expected_stderr == stderr


def test_checksum(tmpdir_ch):
    call_cmd('ia --insecure download nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}

    _stdout, stderr = call_cmd('ia --insecure download --checksum nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    assert f'{prefix} skipping {filepath}, file already exists based on checksum.' == stderr


def test_checksum_archive(tmpdir_ch):
    call_cmd('ia --insecure download nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}

    _stdout, stderr = call_cmd('ia --insecure download --checksum-archive nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    assert f'{prefix} skipping {filepath}, file already exists based on checksum.' == stderr

    assert '_checksum_archive.txt' in files_downloaded('.')
    with open(os.path.join('.', '_checksum_archive.txt'), encoding='utf-8') as f:
        filepath = os.path.join('nasa', 'nasa_meta.xml')
        assert f.read() == f'{filepath}\n'

    _stdout, stderr = call_cmd('ia --insecure download --checksum-archive nasa nasa_meta.xml')
    assert files_downloaded('nasa') == {'nasa_meta.xml'}
    prefix = 'nasa:\n'.replace('\n', os.linesep)
    filepath = os.path.join('nasa', 'nasa_meta.xml')
    assert f'{prefix} skipping {filepath}, file already exists based on checksum_archive.' == stderr


def test_no_directories(tmpdir_ch):
    call_cmd('ia --insecure download --no-directories nasa nasa_meta.xml')
    assert files_downloaded('.') == {'nasa_meta.xml'}


def test_destdir(tmpdir_ch):
    cmd = 'ia --insecure download --destdir=thisdirdoesnotexist/ nasa nasa_meta.xml'
    _stdout, stderr = call_cmd(cmd, expected_exit_code=2)

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


def test_download_history_flag(capsys):
    """Test that --download-history correctly includes/excludes history files.

    Regression test for https://github.com/jjjake/internetarchive/issues/735
    The bug was that --download-history was being passed directly to ignore_history_dir
    without negation, causing the opposite behavior.
    """
    # Add a history file to the nasa metadata
    nasa_data = json.loads(load_test_data_file('metadata/nasa.json'))
    nasa_data['files'].append({
        'name': 'history/files/old_file.txt',
        'source': 'original',
        'size': '100',
        'format': 'Text',
    })

    with IaRequestsMock() as mocker:
        mocker.add_metadata_mock('nasa', body=json.dumps(nasa_data))
        item = get_item('nasa')

        # Without --download-history (ignore_history_dir=True), history files excluded
        item.download(dry_run=True, ignore_history_dir=True)
        stdout_without = capsys.readouterr().out
        assert 'history/files/old_file.txt' not in stdout_without

        # With --download-history (ignore_history_dir=False), history files included
        item.download(dry_run=True, ignore_history_dir=False)
        stdout_with = capsys.readouterr().out
        assert 'history/files/old_file.txt' in stdout_with


def test_count_views_flag(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='test content')
        ia_call(['ia', '--insecure', 'download', '--no-directories',
                 '--count-views', 'nasa', 'nasa_meta.xml'])
        assert 'cnt=' not in rsps.calls[-1].request.url


def test_default_sends_cnt_zero(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='test content')
        ia_call(['ia', '--insecure', 'download', '--no-directories',
                 'nasa', 'nasa_meta.xml'])
        assert 'cnt=0' in rsps.calls[-1].request.url


@pytest.mark.parametrize(('value', 'expected'), [
    ('0-1023', 'bytes=0-1023'),
    ('bytes=0-1023', 'bytes=0-1023'),
    ('1024-', 'bytes=1024-'),
    ('-5', 'bytes=-5'),
    ('bytes=-1024', 'bytes=-1024'),
    (' 0-100 ', 'bytes=0-100'),
    ('BYTES=5-9', 'bytes=5-9'),
])
def test_normalize_byte_range_valid(value, expected):
    assert normalize_byte_range(value) == expected


@pytest.mark.parametrize('value', ['abc', '-', '5-1', '', 'bytes=', '0-1-2'])
def test_normalize_byte_range_invalid(value):
    with pytest.raises(ValueError, match='range'):
        normalize_byte_range(value)


@pytest.mark.parametrize(('value', 'expected'), [
    ('0-9', ['bytes=0-9']),
    ('0-9,50-99', ['bytes=0-9', 'bytes=50-99']),
    ('bytes=0-9,-100', ['bytes=0-9', 'bytes=-100']),
    (' 0-9 , 50-99 ', ['bytes=0-9', 'bytes=50-99']),
])
def test_parse_byte_ranges_valid(value, expected):
    assert parse_byte_ranges(value) == expected


@pytest.mark.parametrize('value', ['', '0-9,', ',', '0-9,abc', '0-9,,50-99'])
def test_parse_byte_ranges_invalid(value):
    with pytest.raises(ValueError, match='range'):
        parse_byte_ranges(value)


def _range_headers(rsps):
    """Return the Range header of every download request, in call order."""
    return [c.request.headers['Range']
            for c in rsps.calls if 'Range' in c.request.headers]


def test_range_single_bare(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='test')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', '0-3', 'nasa', 'nasa_meta.xml'])
        assert _range_headers(rsps) == ['bytes=0-3']


def test_range_suffix_bare(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='test')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', '-100', 'nasa', 'nasa_meta.xml'])
        assert _range_headers(rsps) == ['bytes=-100']


def test_range_bare_multi_range_one_file(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='AAAA')
        rsps.add(responses.GET, download_url_re, body='BBBB')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', '0-3', '--range', '5-9', 'nasa', 'nasa_meta.xml'])
        # Both ranges, same file, in flag order.
        assert _range_headers(rsps) == ['bytes=0-3', 'bytes=5-9']


def test_range_bare_comma_one_file(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='AAAA')
        rsps.add(responses.GET, download_url_re, body='BBBB')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', '0-3,5-9', 'nasa', 'nasa_meta.xml'])
        # A comma list expands to one request per range, in order -- identical
        # to repeating --range.
        assert _range_headers(rsps) == ['bytes=0-3', 'bytes=5-9']


def test_range_file_form_comma(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='AAAA')
        rsps.add(responses.GET, download_url_re, body='BBBB')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', 'nasa_meta.xml:0-3,5-9', 'nasa'])
        assert _range_headers(rsps) == ['bytes=0-3', 'bytes=5-9']
        urls = [c.request.url for c in rsps.calls if 'Range' in c.request.headers]
        assert all('nasa_meta.xml' in u for u in urls)


def test_range_bare_single_range_multi_file(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='AAAA')
        rsps.add(responses.GET, download_url_re, body='BBBB')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', '0-3', 'nasa', 'nasa_meta.xml', 'globe_west_540.jpg'])
        # Same range applied to each file, in file order.
        assert _range_headers(rsps) == ['bytes=0-3', 'bytes=0-3']
        urls = [c.request.url for c in rsps.calls if 'Range' in c.request.headers]
        assert 'nasa_meta.xml' in urls[0]
        assert 'globe_west_540.jpg' in urls[1]


def test_range_file_form_multi_file(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='AAAA')
        rsps.add(responses.GET, download_url_re, body='BBBB')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', 'nasa_meta.xml:0-3',
                 '--range', 'globe_west_540.jpg:5-9', 'nasa'])
        assert _range_headers(rsps) == ['bytes=0-3', 'bytes=5-9']
        urls = [c.request.url for c in rsps.calls if 'Range' in c.request.headers]
        assert 'nasa_meta.xml' in urls[0]
        assert 'globe_west_540.jpg' in urls[1]


def test_range_file_form_same_file_repeated(tmpdir_ch):
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re, body='AAAA')
        rsps.add(responses.GET, download_url_re, body='BBBB')
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', 'nasa_meta.xml:0-3',
                 '--range', 'nasa_meta.xml:5-9', 'nasa'])
        assert _range_headers(rsps) == ['bytes=0-3', 'bytes=5-9']


@pytest.mark.parametrize('argv', [
    # --range requires --stdout
    ['ia', '--insecure', 'download', 'nasa', 'nasa_meta.xml', '--range', '0-3'],
    # bare range with no file to bind to
    ['ia', '--insecure', 'download', '--stdout', 'nasa', '--range', '0-3'],
    # multiple bare ranges with multiple files is ambiguous
    ['ia', '--insecure', 'download', '--stdout', 'nasa', 'a', 'b',
     '--range', '0-3', '--range', '5-9'],
    # a comma list is multiple ranges too -- still ambiguous with multiple files
    ['ia', '--insecure', 'download', '--stdout', 'nasa', 'a', 'b',
     '--range', '0-3,5-9'],
    # cannot mix bare and FILE: forms
    ['ia', '--insecure', 'download', '--stdout', 'nasa',
     '--range', '0-3', '--range', 'f:5-9'],
    # FILE: form cannot combine with selectors
    ['ia', '--insecure', 'download', '--stdout', 'nasa',
     '--glob', '*', '--range', 'f:0-3'],
    ['ia', '--insecure', 'download', '--stdout', '--itemlist', '/dev/null',
     '--range', 'f:0-3'],
    # cannot read identifiers from stdin with --range
    ['ia', '--insecure', 'download', '--stdout', '-', '--range', 'f:0-3'],
    # invalid range value
    ['ia', '--insecure', 'download', '--stdout', 'nasa', 'nasa_meta.xml',
     '--range', 'not-a-range'],
])
def test_range_invalid_invocations(argv):
    ia_call(argv, expected_exit_code=2)


def test_range_job_failure_exits_nonzero(tmpdir_ch):
    """A failed range segment must propagate a nonzero exit code, so a downstream
    pipe consumer can tell the bytes are incomplete."""
    download_url_re = re.compile(r'https?://archive.org/download/.*')
    with IaRequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add_metadata_mock('nasa')
        rsps.add(responses.GET, download_url_re,
                 status=416,
                 adding_headers={'Content-Range': 'bytes */7105'})
        ia_call(['ia', '--insecure', 'download', '--no-directories', '--stdout',
                 '--range', '99999999-', 'nasa', 'nasa_meta.xml'],
                expected_exit_code=1)


def _range_args(ranges, identifier='nasa', file=None):
    """Build a minimal argparse.Namespace for build_range_jobs unit tests."""
    return argparse.Namespace(
        identifier=identifier, file=file or [], glob=None, format=None,
        source=None, exclude_source=None, search=None, itemlist=None,
        ranges=ranges,
    )


def test_build_range_jobs_filename_with_colon():
    """A FILE:RANGE value whose filename itself contains a colon binds to the
    full filename (split on the last colon)."""
    parser = argparse.ArgumentParser()
    args = _range_args(['weird:name.warc.gz:0-9'])
    assert build_range_jobs(args, parser) == [('weird:name.warc.gz', 'bytes=0-9')]
