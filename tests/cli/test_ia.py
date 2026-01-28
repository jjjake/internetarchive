from tests.conftest import IaRequestsMock, ia_call


def test_ia(capsys):
    ia_call(['ia', '--help'])
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in out

    ia_call(['ia', '--insecure', 'ls', 'nasa'])

    ia_call(['ia', 'nocmd'], expected_exit_code=2)
    out, err = capsys.readouterr()
    assert "invalid choice: 'nocmd'" in err


def test_user_agent_suffix_option():
    """Test that --user-agent-suffix option appends to the default User-Agent."""
    custom_suffix = 'TestCLIAgent/1.0'

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_call(['ia', '--user-agent-suffix', custom_suffix, 'metadata', 'nasa'])
        # Check that the user agent starts with default and ends with custom suffix
        ua = rsps.calls[0].request.headers['User-Agent']
        assert ua.startswith('internetarchive/')
        assert ua.endswith(custom_suffix)
