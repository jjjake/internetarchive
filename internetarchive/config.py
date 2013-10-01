import os

import yaml



# _get_config()
#_____________________________________________________________________________________
def _get_config(config={}):
    home_dir = os.environ.get('HOME')
    if not home_dir:
        return config
    config_file = os.path.join(home_dir, '.config', 'internetarchive.yml')
    try:
        config = yaml.load(open(config_file));
    except IOError:
        config_file = os.path.join(home_dir, '.internetarchive.yml')
        try:
            config = yaml.load(open(config_file))
        except IOError:
            return config
    return config


# get_s3_keys()
#_____________________________________________________________________________________
def get_s3_keys():
    access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    if not access_key or not secret_key:
        config = _get_config()
        s3_config = config.get('s3', {})
        access_key = s3_config.get('access_key')
        secret_key = s3_config.get('secret_key')
    return (access_key, secret_key)


# get_cookies()
#_____________________________________________________________________________________
def get_cookies():
    logged_in_user = os.environ.get('IA_LOGGED_IN_USER')
    logged_in_sig = os.environ.get('IA_LOGGED_IN_SIG')
    if not logged_in_user or not logged_in_sig:
        config = _get_config()
        cookie_config = config.get('cookies', {})
        logged_in_user = cookie_config.get('logged-in-user')
        logged_in_sig = cookie_config.get('logged-in-sig')
    return (logged_in_user, logged_in_sig)
