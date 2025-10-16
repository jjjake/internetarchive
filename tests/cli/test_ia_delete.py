import argparse
import sys

from internetarchive.cli.ia_delete import get_files_to_delete


def make_args(**kwargs):
    args = dict(all=False, file=[], glob=None, format=None, cascade=False)  # noqa: C408
    args.update(kwargs)
    return argparse.Namespace(**args)


def test_get_files_to_delete_all(nasa_item):
    args = make_args(all=True)
    files = list(get_files_to_delete(args, nasa_item))
    expected = {
        'NASAarchiveLogo.jpg',
        'globe_west_540.jpg',
        'nasa_archive.torrent',
        'nasa_files.xml',
        'nasa_meta.xml',
        'nasa_reviews.xml',
    }
    assert {f.name for f in files} == expected


def test_get_files_to_delete_empty_file_list(nasa_item):
    args = make_args(file=[])
    files = list(get_files_to_delete(args, nasa_item))
    expected = {
        'NASAarchiveLogo.jpg',
        'globe_west_540.jpg',
        'nasa_archive.torrent',
        'nasa_files.xml',
        'nasa_meta.xml',
        'nasa_reviews.xml',
    }
    assert {f.name for f in files} == expected


def test_get_files_to_delete_with_glob(nasa_item):
    args = make_args(glob="*xml")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'nasa_meta.xml', 'nasa_reviews.xml', 'nasa_files.xml'}
    assert {f.name for f in files} == expected

    args = make_args(glob="*west_*")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg'}
    assert {f.name for f in files} == expected

    args = make_args(glob="*west_*|*torrent")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg', 'nasa_archive.torrent'}
    assert {f.name for f in files} == expected

    args = make_args(glob="nasa_[!m]*.xml")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'nasa_files.xml', 'nasa_reviews.xml'}
    assert {f.name for f in files} == expected

    args = make_args(glob="nasa_???????.xml")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'nasa_reviews.xml'}
    assert {f.name for f in files} == expected

    args = make_args(glob="*_[0-9]*")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg'}
    assert {f.name for f in files} == expected

    # Match JPEG files with uppercase letters in the name prefix
    args = make_args(glob="[A-Z]*.jpg")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'NASAarchiveLogo.jpg'}
    assert {f.name for f in files} == expected


    # Match lowercase-only names ending in .jpg
    args = make_args(glob="[a-z]*.jpg")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg'}
    assert {f.name for f in files} == expected

    args = make_args(glob="nasa_[fm]*.xml")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'nasa_files.xml', 'nasa_meta.xml'}
    assert {f.name for f in files} == expected


    args = make_args(glob="*.[a-z][a-z][a-z]")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {
        'NASAarchiveLogo.jpg',
        'globe_west_540.jpg',
        'nasa_files.xml',
        'nasa_meta.xml',
        'nasa_reviews.xml'
    }
    assert {f.name for f in files} == expected

    args = make_args(glob="?a*")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {
        'nasa_archive.torrent',
        'nasa_files.xml',
        'nasa_meta.xml',
        'nasa_reviews.xml'
    }
    assert {f.name for f in files} == expected

    args = make_args(glob="g*.jpg")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg'}
    assert {f.name for f in files} == expected

    args = make_args(glob="nasa_*[st].xml")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'nasa_files.xml', 'nasa_reviews.xml'}
    assert {f.name for f in files} == expected

    args = make_args(glob="[!nN]*")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg'}
    assert {f.name for f in files} == expected


def test_get_files_to_delete_with_format(nasa_item):
    args = make_args(format="JPEG")
    files = list(get_files_to_delete(args, nasa_item))
    expected = {'globe_west_540.jpg'}
    assert {f.name for f in files} == expected


def test_get_files_to_delete_with_explicit_file_list(nasa_item):
    args = make_args(file=["nasa_meta.xml", "nasa_reviews.xml"])
    files = list(get_files_to_delete(args, nasa_item))
    expected = {f.name for f in nasa_item.get_files(["nasa_meta.xml", "nasa_reviews.xml"])}
    assert {f.name for f in files} == expected


def test_get_files_to_delete_with_stdin(monkeypatch, nasa_item):
    args = make_args(file=["-"])
    monkeypatch.setattr(sys, "stdin", ["nasa_meta.xml\n", "nasa_reviews.xml\n"])
    files = list(get_files_to_delete(args, nasa_item))
    expected = {f.name for f in nasa_item.get_files(["nasa_meta.xml", "nasa_reviews.xml"])}
    assert {f.name for f in files} == expected
