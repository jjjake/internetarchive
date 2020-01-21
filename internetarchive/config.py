# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2019 Internet Archive
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

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

import os
from collections import defaultdict
from six.moves import configparser

import requests

from internetarchive.exceptions import AuthenticationError
from internetarchive.utils import deep_update
from internetarchive import auth


def get_auth_config(email, password, host=None):
    host = host if host else 'archive.org'
    u = 'https://{}/services/xauthn/'.format(host)
    p = dict(op='login')
    d = dict(email=email, password=password)
    r = requests.post(u, params=p, data=d)
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
            msg = 'Authentication failed: {}'.format(msg)
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


def write_config_file(username, password, config_file=None, host=None):
    config_file, config = parse_config_file(config_file)
    auth_config = get_auth_config(username, password, host)

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
    screenname = auth_config['general']['screenname']
    config.set('general', 'screenname', screenname)

    # Write config file.
    with open(config_file, 'w') as fh:
        os.chmod(config_file, 0o600)
        config.write(fh)

    return config_file


def parse_config_file(config_file=None):
    config = configparser.RawConfigParser()

    if not config_file:
        config_file = os.path.expanduser('~/.config/ia.ini')
        if not os.path.isfile(config_file):
            config_file = os.path.expanduser('~/.ia')
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
        if not config.get('general', 'screenname'):
            config.set('general', 'screenname', None)
    else:
        config.add_section('general')
        config.set('general', 'screenname', None)

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
