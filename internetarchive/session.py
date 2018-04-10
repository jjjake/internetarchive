# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2017 Internet Archive
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
internetarchive.session
~~~~~~~~~~~~~~~~~~~~~~~

This module provides an ArchiveSession object to manage and persist
settings across the internetarchive package.

:copyright: (C) 2012-2018 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
import logging
import locale
import sys
import platform
from time import sleep
try:
    import ujson as json
except ImportError:
    import json

from six import BytesIO
from six.moves import urllib_parse
import pycurl

from internetarchive.config import get_config
from internetarchive.item import Item, Collection
from internetarchive.catalog import Catalog
from internetarchive import __version__
from internetarchive.models import ArchiveRequest, ArchiveResponse


logger = logging.getLogger(__name__)

# TODO: delete this block.
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)


class ArchiveSession(object):
    """The :class:`ArchiveSession <internetarchive.ArchiveSession>`
    object collects together useful functionality from `internetarchive`
    as well as important data such as configuration information and
    credentials.

    Usage::

        >>> from internetarchive import ArchiveSession
        >>> s = ArchiveSession()
        >>> item = s.get_item('nasa')
        Collection(identifier='nasa', exists=True)
    """

    ITEM_MEDIATYPE_TABLE = {
        'collection': Collection,
    }

    def __init__(self,
                 config=None,
                 config_file=None,
                 debug=None):
        """Initialize :class:`ArchiveSession <ArchiveSession>` object with config.

        :type config: dict
        :param config: (optional) A config dict used for initializing the
                       :class:`ArchiveSession <ArchiveSession>` object.

        :type config_file: str
        :param config_file: (optional) Path to config file used for initializing the
                            :class:`ArchiveSession <ArchiveSession>` object.

        :returns: :class:`ArchiveSession` object.
        """
        self.config = get_config(config, config_file)
        self.config_file = config_file
        self.cookies = self.config.get('cookies', {})
        self.secure = self.config.get('general', {}).get('secure', True)
        self.protocol = 'https:' if self.secure else 'http:'
        self.access_key = self.config.get('s3', {}).get('access')
        self.secret_key = self.config.get('s3', {}).get('secret')
        self.headers = self._default_headers()

        logging_config = self.config.get('logging', {})
        if logging_config.get('level'):
            self.set_file_logger(logging_config.get('level', 'NOTSET'),
                                 logging_config.get('file', 'internetarchive.log'))

    def _get_user_agent_string(self):
        """Generate a User-Agent string to be sent with every request."""
        uname = platform.uname()
        try:
            lang = locale.getlocale()[0][:2]
        except:
            lang = ''
        py_version = '{0}.{1}.{2}'.format(*sys.version_info)
        return 'internetarchive/{0} ({1} {2}; N; {3}; {4}) Python/{5}'.format(
            __version__, uname[0], uname[-1], lang, self.access_key, py_version)

    def _default_headers(self):
        cookie_header = ('logged-in-user={logged-in-user}; '
                         'logged-in-sig={logged-in-sig}').format(**self.cookies)
        h = {
                'Authorization': 'LOW {0}:{1}'.format(self.access_key, self.secret_key),
                'Cookie': cookie_header,
                'User-Agent': self._get_user_agent_string(),
        }
        return h

    def _request(self, method, url,
                 params=None, data=None, headers=None, output_file=None, retries=None):
        req = ArchiveRequest(
                method=method.upper(),
                url=url,
                headers=headers,
                output_file=output_file,
        )
        resp = req.send(retries=retries)
        return resp

    def get(self, url, **kwargs):
        return self._request('GET', url, **kwargs)

    def set_file_logger(self, log_level, path, logger_name='internetarchive'):
        """Convenience function to quickly configure any level of
        logging to a file.

        :type log_level: str
        :param log_level: A log level as specified in the `logging` module.

        :type path: string
        :param path: Path to the log file. The file will be created if it doesn't already
                     exist.

        :type logger_name: str
        :param logger_name: (optional) The name of the logger.
        """
        _log_level = {
            'CRITICAL': 50,
            'ERROR': 40,
            'WARNING': 30,
            'INFO': 20,
            'DEBUG': 10,
            'NOTSET': 0,
        }

        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        _log = logging.getLogger(logger_name)
        _log.setLevel(logging.DEBUG)

        fh = logging.FileHandler(path, encoding='utf-8')
        fh.setLevel(_log_level[log_level])

        formatter = logging.Formatter(log_format)
        fh.setFormatter(formatter)

        _log.addHandler(fh)

    def get_item(self, identifier):
        """A method for creating :class:`internetarchive.Item <Item>` and
        :class:`internetarchive.Collection <Collection>` objects.

        :type identifier: str
        :param identifier: A globally unique Archive.org identifier.
        """
        u = '{0}//archive.org/metadata/{1}'.format(self.protocol, identifier)
        r = self.get(u)
        item_metadata = r.json
        mediatype = item_metadata.get('metadata', {}).get('mediatype')
        try:
            item_class = self.ITEM_MEDIATYPE_TABLE.get(mediatype, Item)
        except TypeError:
            item_class = Item
        return item_class(self, identifier, item_metadata)

    def search_items(self, query,
                      fields=None,
                      sorts=None,
                      params=None,
                      max_retries=None):
         """Search for items on Archive.org.

         :type query: str
         :param query: The Archive.org search query to yield results for. Refer to
                       https://archive.org/advancedsearch.php#raw for help formatting your
                       query.

         :type fields: bool
         :param fields: (optional) The metadata fields to return in the search results.

         :type params: dict
         :param params: (optional) The URL parameters to send with each request sent to the
                        Archive.org Advancedsearch Api.

         :returns: A :class:`Search` object, yielding search results.
         """
         # TODO: Make Search pycurl.
         request_kwargs = {} if not request_kwargs else request_kwargs
         return Search(self, query,
                       fields=fields,
                       sorts=sorts,
                       params=params,
                       request_kwargs=request_kwargs,
                       max_retries=max_retries)

    def get_tasks(self,
                  identifier=None,
                  task_id=None,
                  task_type=None,
                  params=None,
                  config=None,
                  verbose=None):
        """Get tasks from the Archive.org catalog. ``internetarchive`` must be configured
        with your logged-in-* cookies to use this function. If no arguments are provided,
        all queued tasks for the user will be returned.

        :type identifier: str
        :param identifier: (optional) The Archive.org identifier for which to retrieve
                           tasks for.

        :type task_id: int or str
        :param task_id: (optional) The task_id to retrieve from the Archive.org catalog.

        :type task_type: str
        :param task_type: (optional) The type of tasks to retrieve from the Archive.org
                          catalog. The types can be either "red" for failed tasks, "blue"
                          for running tasks, "green" for pending tasks, "brown" for paused
                          tasks, or "purple" for completed tasks.

        :type params: dict
        :param params: (optional) The URL parameters to send with each request sent to the
                       Archive.org catalog API.

        :type config: dict
        :param secure: (optional) Configuration options for session.

        :type verbose: bool
        :param verbose: (optional) Set to ``True`` to retrieve verbose information for
                        each catalog task returned. verbose is set to ``True`` by default.

        :returns: A set of :class:`CatalogTask` objects.
        """
         # TODO: Make Catalog pycurl.
        _catalog = Catalog(self,
                           identifier=identifier,
                           task_id=task_id,
                           params=params,
                           config=config,
                           verbose=verbose)
        if task_type:
            return eval('_catalog.{0}_rows'.format(task_type.lower()))
        else:
            return _catalog.tasks

    def s3_is_overloaded(self, identifier=None):
        # TODO: add docstring.
        p = dict(
            check_limit=1,
            accesskey=self.access_key,
            bucket=identifier,
        )
        u = '{0}//s3.us.archive.org?{1}'.format(self.protocol, urllib_parse.urlencode(p))
        try:
            r = self.get(u)
            if r.json.get('over_limit') == 0:
                return False
        except Exception as exc:
            pass
        return True
