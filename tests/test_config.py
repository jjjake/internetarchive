import contextlib
import os
import tempfile
from unittest import mock

import pytest
import requests.adapters
import responses

import internetarchive.config
import internetarchive.session
from internetarchive.exceptions import AuthenticationError


@responses.activate
def test_get_auth_config():
    test_body = """{
        "success": true,
        "values": {
            "cookies": {
                "logged-in-sig": "foo-sig",
                "logged-in-user": "foo%40example.com"
            },
            "email": "foo@example.com",
            "itemname": "@jakej",
            "s3": {
                "access": "Ac3ssK3y",
                "secret": "S3cretK3y"
            },
            "screenname":"jakej"
        },
        "version": 1}"""
    responses.add(responses.POST, 'https://archive.org/services/xauthn/',
                  body=test_body)
    r = internetarchive.config.get_auth_config('test@example.com', 'password1')
    assert r['s3']['access'] == 'Ac3ssK3y'
    assert r['s3']['secret'] == 'S3cretK3y'
    assert r['cookies']['logged-in-user'] == 'foo%40example.com'
    assert r['cookies']['logged-in-sig'] == 'foo-sig'


@responses.activate
def test_get_auth_config_auth_fail():
    # No logged-in-sig cookie set raises AuthenticationError.
    responses.add(responses.POST, 'https://archive.org/services/xauthn/',
                  body='{"error": "failed"}')
    try:
        r = internetarchive.config.get_auth_config('test@example.com', 'password1')
    except AuthenticationError as exc:
        return
        assert str(exc) == ('Authentication failed. Please check your credentials '
                            'and try again.')


def test_get_config():
    config = internetarchive.config.get_config()
    assert isinstance(config, dict)


def test_get_config_with_config_file(tmpdir):
    test_conf = ('[s3]\n'
                 'access = test-access\n'
                 'secret = test-secret\n'
                 '[cookies]\n'
                 'logged-in-sig = test-sig\n'
                 'logged-in-user = test@archive.org\n')

    tmpdir.chdir()
    with open('ia_test.ini', 'w') as fp:
        fp.write(test_conf)

    config = internetarchive.config.get_config(config_file='ia_test.ini',
                                               config={'custom': 'test'})
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test@archive.org'
    assert config['s3']['access'] == 'test-access'
    assert config['s3']['secret'] == 'test-secret'
    assert config['custom'] == 'test'


def test_get_config_no_config_file():
    os.environ['HOME'] = ''
    config = internetarchive.config.get_config()
    assert config == {}


def test_get_config_with_config():
    test_conf = {
        's3': {
            'access': 'custom-access',
            'secret': 'custom-secret',
        },
        'cookies': {
            'logged-in-user': 'test@archive.org',
            'logged-in-sig': 'test-sig',
        },
    }

    os.environ['HOME'] = ''
    config = internetarchive.config.get_config(config=test_conf)
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test@archive.org'
    assert config['s3']['access'] == 'custom-access'
    assert config['s3']['secret'] == 'custom-secret'


def test_get_config_home_not_set():
    os.environ['HOME'] = '/none'
    config = internetarchive.config.get_config()
    assert isinstance(config, dict)


def test_get_config_home_not_set_with_config():
    test_conf = {
        's3': {
            'access': 'no-home-access',
            'secret': 'no-home-secret',
        },
    }
    os.environ['HOME'] = '/none'
    config = internetarchive.config.get_config(config=test_conf)
    assert isinstance(config, dict)
    assert config['s3']['access'] == 'no-home-access'
    assert config['s3']['secret'] == 'no-home-secret'


def test_get_config_config_and_config_file(tmpdir):
    test_conf = ('[s3]\n'
                 'access = test-access\n'
                 'secret = test-secret\n'
                 '[cookies]\n'
                 'logged-in-sig = test-sig\n'
                 'logged-in-user = test@archive.org\n')

    tmpdir.chdir()

    with open('ia_test.ini', 'w') as fp:
        fp.write(test_conf)

    test_conf = {
        's3': {
            'access': 'custom-access',
            'secret': 'custom-secret',
        },
        'cookies': {
            'logged-in-user': 'test@archive.org',
            'logged-in-sig': 'test-sig',
        },
    }
    del test_conf['s3']['access']
    config = internetarchive.config.get_config(config_file='ia_test.ini',
                                               config=test_conf)
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test@archive.org'
    assert config['s3']['access'] == 'test-access'
    assert config['s3']['secret'] == 'custom-secret'


@contextlib.contextmanager
def _environ(**kwargs):
    old_values = {k: os.environ.get(k) for k in kwargs}
    try:
        for k, v in kwargs.items():
            if v is not None:
                os.environ[k] = v
            else:
                del os.environ[k]
        yield
    finally:
        for k, v in old_values.items():
            if v is not None:
                os.environ[k] = v
            else:
                del os.environ[k]


def _test_parse_config_file(
        expected_result,
        config_file_contents='',
        config_file_paths=None,
        home=None,
        xdg_config_home=None,
        config_file_param=None):
    # expected_result: (config_file_path, is_xdg); config isn't compared.
    # config_file_contents: str
    # config_file_paths: list of filenames to write config_file_contents to
    # home: str, override HOME env var; default: path of the temporary dir
    # xdg_config_home: str, set XDG_CONFIG_HOME
    # config_file_param: str, filename to pass to parse_config_file
    # All paths starting with '$TMPTESTDIR/' get evaluated relative to the temp dir.

    if not config_file_paths:
        config_file_paths = []

    with tempfile.TemporaryDirectory() as tmp_test_dir:
        def _replace_path(s):
            if s and s.startswith('$TMPTESTDIR/'):
                return os.path.join(tmp_test_dir, s.split('/', 1)[1])
            return s

        expected_result = (_replace_path(expected_result[0]), expected_result[1])
        config_file_paths = [_replace_path(x) for x in config_file_paths]
        home = _replace_path(home)
        xdg_config_home = _replace_path(xdg_config_home)
        config_file_param = _replace_path(config_file_param)

        for p in config_file_paths:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w') as fp:
                fp.write(config_file_contents)

        if home is None:
            home = tmp_test_dir
        env = {'HOME': home}
        if xdg_config_home is not None:
            env['XDG_CONFIG_HOME'] = xdg_config_home
        with _environ(**env):
            config_file_path, is_xdg, config = internetarchive.config.parse_config_file(
                config_file=config_file_param)

    assert (config_file_path, is_xdg) == expected_result[0:2]


def test_parse_config_file_blank():
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.config/internetarchive/ia.ini', True)
    )


def test_parse_config_file_existing_config_ia():
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.config/ia.ini', False),
        config_file_paths=['$TMPTESTDIR/.config/ia.ini'],
    )


def test_parse_config_file_existing_dotia():
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.ia', False),
        config_file_paths=['$TMPTESTDIR/.ia'],
    )


def test_parse_config_file_existing_config_ia_and_dotia():
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.config/ia.ini', False),
        config_file_paths=['$TMPTESTDIR/.config/ia.ini', '$TMPTESTDIR/.ia'],
    )


def test_parse_config_file_existing_all():
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.config/internetarchive/ia.ini', True),
        config_file_paths=[
            '$TMPTESTDIR/.config/internetarchive/ia.ini',
            '$TMPTESTDIR/.config/ia.ini',
            '$TMPTESTDIR/.ia'
        ],
    )


def test_parse_config_file_custom_xdg():
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.xdg/internetarchive/ia.ini', True),
        xdg_config_home='$TMPTESTDIR/.xdg',
    )


def test_parse_config_file_empty_xdg():
    # Empty XDG_CONFIG_HOME should be treated as if not set, i.e. default
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.config/internetarchive/ia.ini', True),
        xdg_config_home='',
    )


def test_parse_config_file_relative_xdg():
    # Relative XDG_CONFIG_HOME is invalid and should be ignored, i.e. default ~/.config used instead
    _test_parse_config_file(
        expected_result=('$TMPTESTDIR/.config/internetarchive/ia.ini', True),
        xdg_config_home='relative/.config',
    )


def test_parse_config_file_direct_path_overrides_existing_files():
    _test_parse_config_file(
        expected_result=('/path/to/ia.ini', False),
        config_file_paths=[
            '$TMPTESTDIR/.config/internetarchive/ia.ini',
            '$TMPTESTDIR/.config/ia.ini',
            '$TMPTESTDIR/.ia'
        ],
        config_file_param='/path/to/ia.ini',
    )


def test_parse_config_file_with_environment_variable():
    with _environ(IA_CONFIG_FILE='/inexistent.ia.ini'):
        _test_parse_config_file(
            expected_result=('/inexistent.ia.ini', False),
        )


def test_parse_config_file_with_environment_variable_and_parameter():
    with _environ(IA_CONFIG_FILE='/inexistent.ia.ini'):
        _test_parse_config_file(
            expected_result=('/inexistent.other.ia.ini', False),
            config_file_param='/inexistent.other.ia.ini',
        )


def _test_write_config_file(
        expected_config_file,
        expected_modes,
        dirs=None,
        create_expected_file=False,
        config_file_param=None):
    # expected_config_file: str
    # expected_modes: list of (path, mode) tuples
    # dirs: list of str, directories to create before running write_config_file
    # create_expected_file: bool, create the expected_config_file if True
    # config_file_param: str, filename to pass to write_config_file
    # Both dirs and the config file are created with mode 777 (minus umask).
    # All paths are evaluated relative to a temporary HOME.
    # Mode comparison accounts for the umask; expected_modes does not need to care about it.

    with tempfile.TemporaryDirectory() as temp_home_dir:
        expected_config_file = os.path.join(temp_home_dir, expected_config_file)
        if dirs:
            dirs = [os.path.join(temp_home_dir, d) for d in dirs]
        expected_modes = [(os.path.join(temp_home_dir, p), m) for p, m in expected_modes]
        if config_file_param:
            config_file_param = os.path.join(temp_home_dir, config_file_param)
        with _environ(HOME=temp_home_dir):
            # Need to account for the umask in the expected_modes comparisons.
            # The umask can't just be retrieved, so set and then restore previous value.
            umask = os.umask(0)
            os.umask(umask)
            if dirs:
                for d in dirs:
                    os.mkdir(d)
            if create_expected_file:
                with open(expected_config_file, 'w') as fp:
                    os.chmod(expected_config_file, 0o777)
            config_file = internetarchive.config.write_config_file({}, config_file_param)
            assert config_file == expected_config_file
            assert os.path.isfile(config_file)
            for path, mode in expected_modes:
                actual_mode = os.stat(path).st_mode & 0o777
                assert actual_mode == mode & ~umask


def test_write_config_file_blank():
    """Test that a blank HOME is populated with expected dirs and modes."""
    _test_write_config_file(
        expected_config_file='.config/internetarchive/ia.ini',
        expected_modes=[
            ('.config/internetarchive/ia.ini', 0o600),
            ('.config/internetarchive', 0o700),
            ('.config', 0o700),
        ],
    )


def test_write_config_file_config_existing():
    """Test that .config's permissions remain but ia gets created correctly."""
    _test_write_config_file(
        dirs=['.config'],
        expected_config_file='.config/internetarchive/ia.ini',
        expected_modes=[
            ('.config/internetarchive/ia.ini', 0o600),
            ('.config/internetarchive', 0o700),
            ('.config', 0o777),
        ],
    )


def test_write_config_file_config_internetarchive_existing():
    """Test that directory permissions are left as is"""
    _test_write_config_file(
        dirs=['.config', '.config/internetarchive'],
        expected_config_file='.config/internetarchive/ia.ini',
        expected_modes=[
            ('.config/internetarchive/ia.ini', 0o600),
            ('.config/internetarchive', 0o777),
            ('.config', 0o777),
        ],
    )


def test_write_config_file_existing_file():
    """Test that the permissions of the file are forced to 600"""
    _test_write_config_file(
        dirs=['.config', '.config/internetarchive'],
        expected_config_file='.config/internetarchive/ia.ini',
        create_expected_file=True,
        expected_modes=[
            ('.config/internetarchive/ia.ini', 0o600),
            ('.config/internetarchive', 0o777),
            ('.config', 0o777),
        ],
    )


def test_write_config_file_existing_other_file():
    """Test that the permissions of the file are forced to 600 even outside XDG"""
    _test_write_config_file(
        dirs=['foo'],
        expected_config_file='foo/ia.ini',
        create_expected_file=True,
        config_file_param='foo/ia.ini',
        expected_modes=[
            ('foo/ia.ini', 0o600),
            ('foo', 0o777),
        ],
    )


def test_write_config_file_custom_path_existing():
    """Test the creation of a config file at a custom location"""
    _test_write_config_file(
        dirs=['foo'],
        expected_config_file='foo/ia.ini',
        config_file_param='foo/ia.ini',
        expected_modes=[
            ('foo/ia.ini', 0o600),
            ('foo', 0o777),
        ],
    )


def test_write_config_file_custom_path_not_existing():
    """Ensure that an exception is thrown if the custom path dir doesn't exist"""
    with tempfile.TemporaryDirectory() as temp_home_dir:
        with _environ(HOME=temp_home_dir):
            config_file = os.path.join(temp_home_dir, 'foo/ia.ini')
            with pytest.raises(IOError):
                internetarchive.config.write_config_file({}, config_file)
