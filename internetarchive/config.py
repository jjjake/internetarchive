# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

import os
from collections import defaultdict
from six.moves import configparser

import requests

from internetarchive.exceptions import AuthenticationError
from internetarchive.utils import deep_update


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
            raise AuthenticationError('Authentication failed. '
                                      'Please check your credentials and try again.')

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
                'access': j['key']['s3accesskey'],
                'secret': j['key']['s3secretkey'],
            },
            'cookies': {
                'logged-in-user': s.cookies['logged-in-user'],
                'logged-in-sig': s.cookies['logged-in-sig'],
            }
        }

    return auth_config


def write_config_file(username, password, config_file=None):
    config_file, config = parse_config_file(config_file)
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
        os.chmod(config_file, 0o600)
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
    if config.has_section('general'):
        for k, v in config.items('general'):
            if k in ['secure']:
                config.set('general', k, config.getboolean('general', k))

    return (config_file, config)


def get_config(config=None, config_file=None):
    _config = {} if not config else config
    config_file, config = parse_config_file(config_file)

    if not os.path.isfile(config_file):
        return _config

    config_dict = defaultdict(dict)
    for sec in config.sections():
        try:
            for k, v in config.items(sec):
                if k is None or v is None:
                    continue
                config_dict[sec][k] = v
        except TypeError:
            pass

    # Recursive/deep update.
    deep_update(config_dict, _config)

    return dict((k, v) for k, v in config_dict.items() if v is not None)
