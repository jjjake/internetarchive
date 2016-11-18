from copy import deepcopy

from internetarchive import get_session
from internetarchive.cli import ia_list
from tests.conftest import IaRequestsMock

SESSION = get_session()

NASA_FILES = set([
    'NASAarchiveLogo.jpg',
    'globe_west_540.jpg',
    'nasa_reviews.xml',
    'nasa_meta.xml',
    'nasa_archive.torrent',
    'nasa_files.xml'
])


def test_ia_list(capsys, nasa_mocker):
    ia_list.main(['list', 'nasa'], SESSION)
    out, err = capsys.readouterr()
    assert set([l for l in out.split('\n') if l]) == NASA_FILES


def test_ia_list_verbose(capsys, nasa_mocker):
    ia_list.main(['list', '--verbose', 'nasa'], SESSION)

    out, err = capsys.readouterr()
    _nasa_files = deepcopy(NASA_FILES)
    _nasa_files.add('name')
    assert set([l for l in out.split('\n') if l]) == _nasa_files


def test_ia_list_all(capsys, nasa_mocker):
    ia_list.main(['list', '--all', 'nasa'], SESSION)

    out, err = capsys.readouterr()
    out = [l for l in out.split('\n') if l]
    assert len(out) == 6
    assert all(len(f.split('\t')) == 9 for f in out)
    assert all(f.split('\t')[0] in NASA_FILES for f in out)


def test_ia_list_location(capsys, nasa_mocker):
    ia_list.main(['list', '--location', '--glob', '*meta.xml', 'nasa'], SESSION)
    out, err = capsys.readouterr()
    assert out == 'https://archive.org/download/nasa/nasa_meta.xml\n'


def test_ia_list_columns(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_list.main(['list', '--columns', 'name,md5', '--glob', '*meta.xml', 'nasa'],
                     SESSION)

    out, err = capsys.readouterr()
    assert out == 'nasa_meta.xml\t0e339f4a29a8bc42303813cbec9243e5\n'

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_list.main(['list', '--columns', 'md5', '--glob', '*meta.xml', 'nasa'], SESSION)

    out, err = capsys.readouterr()
    assert out == '0e339f4a29a8bc42303813cbec9243e5\n'


def test_ia_list_glob(capsys, nasa_mocker):
    ia_list.main(['list', '--glob', '*torrent', 'nasa'], SESSION)
    out, err = capsys.readouterr()
    assert out == 'nasa_archive.torrent\n'


def test_ia_list_format(capsys, nasa_mocker):
    ia_list.main(['list', '--format', 'Metadata', 'nasa'], SESSION)

    out, err = capsys.readouterr()
    expected_output = set([
        'nasa_reviews.xml',
        'nasa_files.xml',
        'nasa_meta.xml',
    ])
    assert set([f for f in out.split('\n') if f]) == expected_output


def test_ia_list_non_existing(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', body="{}")
        try:
            ia_list.main(['list', 'nasa'], SESSION)
        except SystemExit as exc:
            assert exc.code == 1

    out, err = capsys.readouterr()
    assert out == ''
