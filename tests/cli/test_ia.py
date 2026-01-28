from tests.conftest import IaRequestsMock, ia_call


def test_ia(capsys):
    ia_call(['ia', '--help'])
    out, err = capsys.readouterr()
    assert 'A command line interface to Archive.org.' in out

    ia_call(['ia', '--insecure', 'ls', 'nasa'])

    ia_call(['ia', 'nocmd'], expected_exit_code=2)
    out, err = capsys.readouterr()
    assert "invalid choice: 'nocmd'" in err


def test_user_agent_option():
    """Test that --user-agent option sets the User-Agent header."""
    custom_ua = 'TestCLIAgent/1.0'

    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('nasa')
        ia_call(['ia', '--user-agent', custom_ua, 'metadata', 'nasa'])
        # Check that our custom user agent was sent in the request
        assert rsps.calls[0].request.headers['User-Agent'] == custom_ua
