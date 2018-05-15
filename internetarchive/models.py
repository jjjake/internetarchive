# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2018 Internet Archive
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
internetarchive.models
~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2018 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
import os
import json
from six import BytesIO
import logging

from six.moves import urllib_parse
import six
import pycurl


logger = logging.getLogger(__name__)


class ArchiveRequest(object):

    def __init__(self, curl_instance=None, method=None, url=None, headers=None,
                 input_file_obj=None, data=None, params=None, metadata=None,
                 source_metadata=None, target=None, priority=None, append=None,
                 append_list=None, verbose=False, output_file=None, access_key=None,
                 secret_key=None, timeout=None, connect_timeout=None):
        headers = headers if headers else dict()
        self.params = params if params else dict()
        self.c = curl_instance if curl_instance else pycurl.Curl()
        self.headers = headers if headers else dict()
        self.data = data if data else dict()
        self.body = None
        self.access_key = access_key
        self.secret_key = secret_key

        if not output_file:
            self.output_file = None
            self._buffer = BytesIO()
            self.c.setopt(self.c.WRITEDATA, self._buffer)
        else:
            self._buffer = None
            if os.path.exists(output_file):
                self.output_file = open(output_file, 'ab')
                self.c.setopt(self.c.RESUME_FROM, os.path.getsize(output_file))
            else:
                self.output_file = open(output_file, 'wb')
            self.c.setopt(self.c.WRITEDATA, self.output_file)
            self.c.setopt(self.c.NOPROGRESS, False)

        if timeout:
            self.c.setopt(self.c.TIMEOUT, int(timeout))
        if connect_timeout:
            self.c.setopt(self.c.CONNECTTIMEOUT, int(connect_timeout))

        if self.params:
            self.url = '{0}?{1}'.format(url, urllib_parse.urlencode(self.params))
        else:
            self.url = url
        self.c.setopt(self.c.URL, self.url)
        self.c.setopt(self.c.FOLLOWLOCATION, 1)

        self.prepare_headers()
        self.headers.update(headers)

        if method == 'POST':
            self.prepare_body()

        if method == 'PUT':
            self.c.setopt(self.c.READFUNCTION, input_file_obj.read)
            self.c.setopt(self.c.CUSTOMREQUEST, "PUT")
            self.c.setopt(self.c.POST, 1)
            self.c.setopt(self.c.NOPROGRESS, False)

        if verbose:
            self.c.setopt(self.c.VERBOSE, True)

    def prepare_headers(self):
        prepared_headers = list()
        for key in self.headers:
            h = '{0}: {1}'.format(key, self.headers[key])
            prepared_headers.append(h)
        self.c.setopt(pycurl.HTTPHEADER, prepared_headers)

    def prepare_body(self):
        self.body = urllib_parse.urlencode(self.data)
        self.c.setopt(pycurl.POSTFIELDS, self.body)


class ArchiveResponse(object):

    def __init__(self, request):
        self.c = request.c
        self._buffer = request._buffer
        self.headers = dict()
        self.status_code = None
        self.request = request

        self._body = None
        self._text = None
        self._json = None

    def __repr__(self):
        return r'<ArchiveResponse [{}]>'.format(self.status_code)

    @property
    def body(self):
        if not self._body:
            if not self.request.output_file:
                self._body = self._buffer.getvalue()
        return self._body

    @property
    def text(self):
        if not self._text:
            if not self.request.output_file:
                self._text = self._buffer.getvalue().decode('utf-8')
        return self._text

    @property
    def json(self):
        if not self._json:
            try:
                self._json = json.loads(self.body)
            except ValueError:
                return dict()
        return self._json

    def close(self):
        self.c.close()

    def header_function(self, header_line):
        # HTTP standard specifies that headers are encoded in iso-8859-1.
        # On Python 2, decoding step can be skipped.
        # On Python 3, decoding step is required.
        if six.PY2:
            header_line = header_line
        else:
            header_line = header_line.decode('iso-8859-1')

        # Header lines include the first status line (HTTP/1.x ...).
        # We are going to ignore all lines that don't have a colon in them.
        # This will botch headers that are split on multiple lines...
        if ':' not in header_line:
            return

        # Break the header line into header name and value.
        name, value = header_line.split(':', 1)

        # Remove whitespace that may be present.
        # Header lines include the trailing newline, and there may be whitespace
        # around the colon.
        name = name.strip()
        value = value.strip()

        # Header names are case insensitive.
        # Lowercase name here.
        name = name.lower()

        # Now we can actually record the header name and value.
        # Note: this only works when headers are not duplicated, see below.
        if name in self.headers:
            if isinstance(self.headers[name], list):
                self.headers[name].append(value)
            else:
                self.headers[name] = [self.headers[name], value]
        else:
            self.headers[name] = value
