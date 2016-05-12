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
internetarchive.auth
~~~~~~~~~~~~~~~~~~~~

This module contains the Archive.org authentication handlers for Requests.

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from requests.auth import AuthBase


class S3Auth(AuthBase):
    """Attaches S3 Basic Authentication to the given Request object."""
    def __init__(self, access_key=None, secret_key=None):
        self.access_key = access_key
        self.secret_key = secret_key

    def __call__(self, r):
        auth_str = 'LOW {a}:{s}'.format(a=self.access_key, s=self.secret_key)
        r.headers['Authorization'] = auth_str
        return r


class S3PostAuth(AuthBase):
    """Attaches S3 Basic Authentication to the given Request object."""
    def __init__(self, access_key=None, secret_key=None):
        self.access_key = access_key
        self.secret_key = secret_key

    def __call__(self, r):
        auth_str = '&access={a}&secret={s}'.format(a=self.access_key, s=self.secret_key)
        if not r.body:
            r.body = ''
        r.body += auth_str
        r.headers['content-type'] = 'application/x-www-form-urlencoded'
        return r
