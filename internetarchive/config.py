import os

import yaml


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
