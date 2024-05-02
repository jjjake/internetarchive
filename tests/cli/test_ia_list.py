from copy import deepcopy

from tests.conftest import IaRequestsMock, ia_call

NASA_FILES = {
    'NASAarchiveLogo.jpg',
    'globe_west_540.jpg',
    'nasa_reviews.xml',
    'nasa_meta.xml',
    'nasa_archive.torrent',
    'nasa_files.xml'
}


def test_ia_list(capsys, nasa_mocker):
    ia_call(['ia', 'list', 'nasa'])
    out, err = capsys.readouterr()
    assert {l for l in out.split('\n') if l} == NASA_FILES


def test_ia_list_verbose(capsys, nasa_mocker):
    ia_call(['ia', 'list', '--verbose', 'nasa'])

    out, err = capsys.readouterr()
    _nasa_files = deepcopy(NASA_FILES)
    _nasa_files.add('name')
    assert {l for l in out.split('\n') if l} == _nasa_files


def test_ia_list_all(capsys, nasa_mocker):
    ia_call(['ia', 'list', '--all', 'nasa'])

    out, err = capsys.readouterr()
    out = [l for l in out.split('\n') if l]
    assert len(out) == 6
    assert all(len(f.split('\t')) == 9 for f in out)
    assert all(f.split('\t')[0] in NASA_FILES for f in out)


def test_ia_list_location(capsys, nasa_mocker):
    ia_call(['ia', 'list', '--location', '--glob', '*meta.xml', 'nasa'])
    out, err = capsys.readouterr()
    assert out == 'https://archive.org/download/nasa/nasa_meta.xml\n'


def test_ia_list_columns(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_call(['ia', 'list', '--columns', 'name,md5', '--glob', '*meta.xml', 'nasa'])

    out, err = capsys.readouterr()
    assert out == 'nasa_meta.xml\t0e339f4a29a8bc42303813cbec9243e5\n'

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_call(['ia', 'list', '--columns', 'md5', '--glob', '*meta.xml', 'nasa'])

    out, err = capsys.readouterr()
    assert out == '0e339f4a29a8bc42303813cbec9243e5\n'


def test_ia_list_glob(capsys, nasa_mocker):
    ia_call(['ia', 'list', '--glob', '*torrent', 'nasa'])
    out, err = capsys.readouterr()
    assert out == 'nasa_archive.torrent\n'


def test_ia_list_format(capsys, nasa_mocker):
    ia_call(['ia', 'list', '--format', 'Metadata', 'nasa'])

    out, err = capsys.readouterr()
    expected_output = {
        'nasa_reviews.xml',
        'nasa_files.xml',
        'nasa_meta.xml',
    }
    assert {f for f in out.split('\n') if f} == expected_output


def test_ia_list_non_existing(capsys):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa', body='{}')
        ia_call(['ia', 'list', 'nasa'], expected_exit_code=1)

    out, err = capsys.readouterr()
    assert out == ''
