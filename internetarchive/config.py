#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.config
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import os
from collections import defaultdict
from configparser import RawConfigParser
from time import sleep
from typing import DefaultDict, Dict, Mapping

import requests

from internetarchive import auth
from internetarchive.exceptions import AuthenticationError
from internetarchive.utils import deep_update


def get_auth_config(email: str, password: str, host: str = 'archive.org') -> dict:
    u = f'https://{host}/services/xauthn/'
    p = {'op': 'login'}
    d = {'email': email, 'password': password}
    r = requests.post(u, params=p, data=d, timeout=10)
    sleep(2)
    j = r.json()
    if not j.get('success'):
        try:
            msg = j['values']['reason']
        except KeyError:
            msg = j['error']
        if msg == 'account_not_found':
            msg = 'Account not found, check your email and try again.'
        elif msg == 'account_bad_password':
            msg = 'Incorrect password, try again.'
        else:
            msg = f'Authentication failed: {msg}'
        raise AuthenticationError(msg)
    auth_config = {
        's3': {
            'access': j['values']['s3']['access'],
            'secret': j['values']['s3']['secret'],
        },
        'cookies': {
            'logged-in-user': j['values']['cookies']['logged-in-user'],
            'logged-in-sig': j['values']['cookies']['logged-in-sig'],
        },
        'general': {
            'screenname': j['values']['screenname'],
        }
    }
    return auth_config


def write_config_file(auth_config: Mapping, config_file=None):
    config_file, is_xdg, config = parse_config_file(config_file)

    # S3 Keys.
    access = auth_config.get('s3', {}).get('access')
    secret = auth_config.get('s3', {}).get('secret')
    config.set('s3', 'access', access)
    config.set('s3', 'secret', secret)

    # Cookies.
    cookies = auth_config.get('cookies', {})
    config.set('cookies', 'logged-in-user', cookies.get('logged-in-user'))
    config.set('cookies', 'logged-in-sig', cookies.get('logged-in-sig'))

    # General.
    screenname = auth_config.get('general', {}).get('screenname')
    config.set('general', 'screenname', screenname)

    # Create directory if needed.
    config_directory = os.path.dirname(config_file)
    if is_xdg and not os.path.exists(config_directory):
        # os.makedirs does not apply the mode for intermediate directories since Python 3.7.
        # The XDG Base Dir spec requires that the XDG_CONFIG_HOME directory be created with mode 700.
        # is_xdg will be True iff config_file is ${XDG_CONFIG_HOME}/internetarchive/ia.ini.
        # So create grandparent first if necessary then parent to ensure both have the right mode.
        os.makedirs(os.path.dirname(config_directory), mode=0o700, exist_ok=True)
        os.mkdir(config_directory, 0o700)

    # Write config file.
    with open(config_file, 'w') as fh:
        os.chmod(config_file, 0o600)
        config.write(fh)

    return config_file


def parse_config_file(config_file=None):
    config = RawConfigParser()

    is_xdg = False
    if not config_file:
        candidates = []
        if os.environ.get('IA_CONFIG_FILE'):
            candidates.append(os.environ['IA_CONFIG_FILE'])
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        if not xdg_config_home or not os.path.isabs(xdg_config_home):
            # Per the XDG Base Dir specification, this should be $HOME/.config. Unfortunately, $HOME
            # does not exist on all systems. Therefore, we use ~/.config here. On a POSIX-compliant
            # system, where $HOME must always be set, the XDG spec will be followed precisely.
            xdg_config_home = os.path.join(os.path.expanduser('~'), '.config')
        xdg_config_file = os.path.join(xdg_config_home, 'internetarchive', 'ia.ini')
        candidates.append(xdg_config_file)
        candidates.append(os.path.join(os.path.expanduser('~'), '.config', 'ia.ini'))
        candidates.append(os.path.join(os.path.expanduser('~'), '.ia'))
        for candidate in candidates:
            if os.path.isfile(candidate):
                config_file = candidate
                break
        else:
            # None of the candidates exist, default to IA_CONFIG_FILE if set else XDG
            config_file = os.environ.get('IA_CONFIG_FILE', xdg_config_file)
        if config_file == xdg_config_file:
            is_xdg = True
    config.read(config_file)

    if not config.has_section('s3'):
        config.add_section('s3')
        config.set('s3', 'access', None)
        config.set('s3', 'secret', None)
    if not config.has_section('cookies'):
        config.add_section('cookies')
        config.set('cookies', 'logged-in-user', None)
        config.set('cookies', 'logged-in-sig', None)

    if config.has_section('general'):
        for k, _v in config.items('general'):
            if k in ['secure']:
                config.set('general', k, config.getboolean('general', k))
        if not config.get('general', 'screenname'):
            config.set('general', 'screenname', None)
    else:
        config.add_section('general')
        config.set('general', 'screenname', None)

    return (config_file, is_xdg, config)


def get_config(config=None, config_file=None) -> dict:
    _config = config or {}
    config_file, _is_xdg, config_parser = parse_config_file(config_file)

    # TODO: Use typing.TypedDict when we drop Python 3.8 support
    # to get rid of noqa: UP006
    config_dict: DefaultDict[str, Dict[str, str]] = defaultdict(dict)  # noqa: UP006

    # Read from config file if it exists
    if os.path.isfile(config_file):
        for sec in config_parser.sections():
            try:
                for k, v in config_parser.items(sec):
                    if k is None or v is None:
                        continue
                    config_dict[sec][k] = v
            except TypeError:
                pass

    # Check environment variables and override S3 config if present
    env_access_key = os.environ.get('IA_ACCESS_KEY_ID')
    env_secret_key = os.environ.get('IA_SECRET_ACCESS_KEY')

    # Check if only one environment variable is set
    if (env_access_key and not env_secret_key) or (not env_access_key and env_secret_key):
        raise ValueError(
            "Both IA_ACCESS_KEY_ID and IA_SECRET_ACCESS_KEY environment variables "
            "must be set together, or neither should be set."
        )

    if env_access_key and env_secret_key:
        config_dict['s3']['access'] = env_access_key
        config_dict['s3']['secret'] = env_secret_key

    # Recursive/deep update with passed config
    deep_update(config_dict, _config)

    return {k: v for k, v in config_dict.items() if v is not None}
