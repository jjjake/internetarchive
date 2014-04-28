import os

import yaml


# get_config()
#_____________________________________________________________________________________
def get_config(config=None, config_file=None):
    """Retrieve user configuration from a file. If a file is not
    given, looks in "$HOME/.config/internetarchive.yml" and
    "$HOME/.internetarchive.yml", in that order.

    :type config: dict
    :param config: (optional) Configuration options to override
                   those retrieved from the file.

    :type config_file: str
    :param config_file: (optional) Path to configuration file.

    :rtype: dict
    :returns: A dictionary of the configuration values.

    """
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
