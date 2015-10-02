import os
from six.moves import configparser

import requests

from .exceptions import AuthenticationError
from .utils import deep_update


def get_auth_config(username, password):
    payload = dict(
        username=username,
        password=password,
        remember='CHECKED',
        action='login',
    )

    with requests.Session() as s:
        # Attache logged-in-* cookies to Session.
        u = 'https://archive.org/account/login.php'
        r = s.post(u, data=payload, cookies={'test-cookie': '1'})

        if 'logged-in-sig' not in s.cookies:
            raise AuthenticationError(
                    'Authentication failed. Please check your credentials and try again.')

        # Get S3 keys.
        u = 'https://archive.org/account/s3.php'
        p = dict(output_json=1)
        r = s.get(u, params=p)
        j = r.json()

        auth_config = {
            's3': {
                'access': j['key']['s3accesskey'],
                'secret': j['key']['s3secretkey'],
            },
            'cookies': {
                'logged-in-user': s.cookies['logged-in-user'],
                'logged-in-sig': s.cookies['logged-in-sig'],
            }
        }

    return auth_config


def write_config_file(username, password):
    config_file, config = parse_config_file()
    auth_config = get_auth_config(username, password)

    # S3 Keys.
    access = auth_config.get('s3', {}).get('access')
    secret = auth_config.get('s3', {}).get('secret')
    config.set('s3', 'access', access)
    config.set('s3', 'secret', secret)

    # Cookies.
    cookies = auth_config.get('cookies', {})
    config.set('cookies', 'logged-in-user', cookies.get('logged-in-user'))
    config.set('cookies', 'logged-in-sig', cookies.get('logged-in-sig'))

    # Write config file.
    with open(config_file, 'w') as fh:
        os.chmod(config_file, 0o700)
        config.write(fh)

    return config_file


def parse_config_file(config_file=None):
    config = configparser.RawConfigParser()

    if not config_file:
        config_dir = os.path.expanduser('~/.config')
        if not os.path.isdir(config_dir):
            config_file = os.path.expanduser('~/.ia')
        else:
            config_file = '{0}/ia.ini'.format(config_dir)
    config.read(config_file)

    if not config.has_section('s3'):
        config.add_section('s3')
        config.set('s3', 'access', None)
        config.set('s3', 'secret', None)
    if not config.has_section('cookies'):
        config.add_section('cookies')
        config.set('cookies', 'logged-in-user', None)
        config.set('cookies', 'logged-in-sig', None)
    if not config.has_section('logging'):
        config.add_section('logging')
        config.set('logging', 'level', 'ERROR')
        config.set('logging', 'file', 'internetarchive.log')

    return (config_file, config)


def get_config(config=None, config_file=None):
    _config = {} if not config else config
    config_file, config = parse_config_file(config_file)

    if not os.path.isfile(config_file):
        return _config

    config_dict = dict()
    for sec in config.sections():
        try:
            _items = [(k, v) for k, v in config.items(sec) if k and v] 
            config_dict[sec] = dict(_items)
        except TypeError:
            pass

    # Recursive/deep update.
    deep_update(config_dict, _config)

    return dict((k, v) for k, v in config_dict.items() if v)
