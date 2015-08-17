import os

import requests
import yaml



# get_config()
# ____________________________________________________________________________________
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

        # Get S3 keys.
        u = 'https://archive.org/account/s3.php'
        p = dict(output_json=1)
        r = s.get(u, params=p)
        j = r.json()

        if not j or not j.get('key'):
            raise requests.exceptions.HTTPError(
                'Authorization failed. Please check your credentials and try again.')

        auth_config = {
            's3': {
                'access_key': j['key']['s3accesskey'],
                'secret_key': j['key']['s3secretkey'],
            },
            'cookies': {
                'logged-in-user': s.cookies['logged-in-user'],
                'logged-in-sig': s.cookies['logged-in-sig'],
            }
        }

    return auth_config


# get_config()
# ____________________________________________________________________________________
def get_config(config=None, config_file=None):
    config = {} if not config else config
    if not config_file:
        home_dir = os.environ.get('HOME')
        if not home_dir:
            return config
        config_file = os.path.join(home_dir, '.config', 'internetarchive.yml')
    try:
        _config = yaml.load(open(config_file))
    except IOError:
        config_file = os.path.join(home_dir, '.internetarchive.yml')
        try:
            _config = yaml.load(open(config_file))
        except IOError:
            _config = {}
    final_config = _config.copy()
    final_config.update(config)
    return final_config
