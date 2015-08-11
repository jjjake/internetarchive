import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import responses

import internetarchive.config
import internetarchive.session
from internetarchive.exceptions import AuthenticationError


@responses.activate
def test_get_auth_config():
    def request_callback(request):
        headers = {'set-cookie': 'logged-in-user=test%40archive.org; logged-in-sig=test-sig;'}
        return (200, headers, '')

    responses.add(responses.POST, 'https://archive.org/account/login.php',
                  adding_headers={'set-cookie': 'logged-in-user=test%40archive.org; logged-in-sig=test-sig;'})
    #responses.add_callback(responses.POST, 'https://archive.org/account/login.php', request_callback)
              #adding_headers={'set-cookie': 'logged-in-user=test%40archive.org; logged-in-sig=test-sig;'})

    test_body = """{
        "key": {
            "s3secretkey": "test-secret",
            "s3accesskey": "test-access"
        }, 
        "success": 1
    }"""
    responses.add(responses.GET, 'https://archive.org/account/s3.php',
              status=200,
              body=test_body,
              adding_headers={'set-cookie': 'logged-in-user=test%40archive.org; logged-in-sig=test-sig;'},
              content_type='application/json')

    r = internetarchive.config.get_auth_config('test@example.com', 'password1')
    assert r['s3']['access'] == 'test-access'
    assert r['s3']['secret'] == 'test-secret'
    assert r['cookies']['logged-in-user'] == 'test@archive.org'
    assert r['cookies']['logged-in-sig'] == 'test-sig'


@responses.activate
def test_get_auth_config_auth_fail():
    # No logged-in-sig cookie set raises AuthenticationError.
    responses.add(responses.POST, 'https://archive.org/account/login.php', status=200)
    try:
        r = internetarchive.config.get_auth_config('test@example.com', 'password1')
    except AuthenticationError as exc:
        assert str(exc) == 'Authentication failed. Please check your credentials and try again.'


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
    config = internetarchive.config.get_config(config_file='ia_test.ini', config=test_conf)
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test@archive.org'
    assert config['s3']['access'] == 'test-access'
    assert config['s3']['secret'] == 'custom-secret'
