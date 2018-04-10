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
import json
import pycurl
from six import BytesIO
import logging
from time import sleep


logger = logging.getLogger(__name__)


class ArchiveRequest(object):

    def __init__(self, method, url,
                 headers=None,
                 verbose=False,
                 output_file=None):
        self.c = pycurl.Curl()
        self.headers = headers if headers else dict()
        if not output_file:
            self.output_file = None
            self._buffer = BytesIO()
            self.c.setopt(self.c.WRITEDATA, self._buffer)
        else:
            self._buffer = None
            self.output_file = output_file
            self.c.setopt(pycurl.WRITEDATA, self.output_file)

        self.c.setopt(self.c.URL, url)
        self.c.setopt(self.c.FOLLOWLOCATION, 1)
        self.prepare_headers()

        #self.headers.update(headers)

        if verbose:
            self.c.setopt(self.c.VERBOSE, True)

    def prepare_headers(self):
        prepared_headers = list()
        for key in self.headers:
            h = '{0}: {1}'.format(key, self.headers[key])
            prepared_headers.append(h)
        self.c.setopt(pycurl.HTTPHEADER, prepared_headers)


    def send(self, retries=None, status_forcelist=None):
        if not status_forcelist:
            status_forcelist = [500, 501, 502, 503, 504]
        retries = 3 if retries is None else retries

        tries = 1
        backoff=2
        while True:
            sleep_time = (tries*backoff)
            self.c.perform()
            status_code = self.c.getinfo(self.c.RESPONSE_CODE)

            if status_code == 200:
                break
            elif status_code in status_forcelist:
                if tries > retries:
                    break
                logger.warning('Retrying')
                sleep(sleep_time)
                pass
            else:
                break

            tries += 1

        return ArchiveResponse(self)


class ArchiveResponse(object):

    def __init__(self, request):
        self.c = request.c
        self._buffer = request._buffer
        self.status_code = self.c.getinfo(self.c.RESPONSE_CODE)

        self._json = None
        if not request.output_file:
            self.body = self._buffer.getvalue().decode('utf-8')

    def __repr__(self):
        return r'<ArchiveResponse [{}]>'.format(self.status_code)

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
