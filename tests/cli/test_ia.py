from tests.conftest import ia_call


def test_ia(capsys):
    ia_call(['ia', '--help'])
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in out

    ia_call(['ia', '--insecure', 'ls', 'nasa'])

    ia_call(['ia', 'nocmd'], expected_exit_code=127)
    out, err = capsys.readouterr()
    assert "error: 'nocmd' is not an ia command!" in err

    ia_call(['ia', 'help'])
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in err

    ia_call(['ia', 'help', 'list'])
