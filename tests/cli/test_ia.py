import sys

from internetarchive.cli import ia


def test_ia(capsys):
    sys.argv = ['ia', '--help']
    try:
        ia.main()
    except SystemExit as exc:
        assert not exc.code
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in out

    try:
        sys.argv = ['ia', '--insecure', 'ls', 'nasa']
        ia.main()
    except SystemExit as exc:
        assert not exc.code

    try:
        sys.argv = ['ia', 'nocmd']
        ia.main()
    except SystemExit as exc:
        assert exc.code == 127
    out, err = capsys.readouterr()
    assert "error: 'nocmd' is not an ia command!" in err

    try:
        sys.argv = ['ia', 'help']
        ia.main()
    except SystemExit as exc:
        assert not exc.code
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in err

    try:
        sys.argv = ['ia', 'help', 'list']
        ia.main()
    except SystemExit as exc:
        assert not exc.code
