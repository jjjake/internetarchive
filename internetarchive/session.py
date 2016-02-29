# -*- coding: utf-8 -*-
"""
internetarchive.session
~~~~~~~~~~~~~~~~~~~~~~~

This module provides an ArchiveSession object to manage and persist
settings across the internetarchive package.

:copyright: (c) 2015 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals

import os
import locale
import sys
import logging

import requests.sessions
from requests.utils import default_headers
from requests.adapters import HTTPAdapter
from requests.packages.urllib3 import Retry

from internetarchive import __version__
from internetarchive.config import get_config
from internetarchive.item import Item, Collection
from internetarchive.search import Search
from internetarchive.catalog import Catalog


logger = logging.getLogger(__name__)


class ArchiveSession(requests.sessions.Session):
    """The :class:`ArchiveSession <internetarchive.ArchiveSession>`
    object collects together useful functionality from `internetarchive`
    as well as important data such as configuration information and
    credentials.  It is subclassed from
    :class:`requests.Session <requests.Session>`.

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
                 debug=None,
                 http_adapter_kwargs=None):
        """Initialize :class:`ArchiveSession <ArchiveSession>` object with config.

        :type config: dict
        :param config: (optional) A config dict used for initializing the
                       :class:`ArchiveSession <ArchiveSession>` object.

        :type config_file: str
        :param config_file: (optional) Path to config file used for initializing the
                            :class:`ArchiveSession <ArchiveSession>` object.

        :type http_adapter_kwargs: dict
        :param http_adapter_kwargs: (optional) Keyword arguments used to initialize the
                                    :class:`requests.adapters.HTTPAdapter <HTTPAdapter>`
                                    object.

        :returns: :class:`ArchiveSession` object.
        """
        super(ArchiveSession, self).__init__()
        http_adapter_kwargs = {} if not http_adapter_kwargs else http_adapter_kwargs
        debug = False if not debug else True

        self.config = get_config(config, config_file)
        self.cookies.update(self.config.get('cookies', {}))
        # Avoid InsecurePlatformWarning errors on older versions of Python.
        if sys.version_info < (2, 7, 9):
            self.secure = self.config.get('general', {}).get('secure', False)
        else:
            self.secure = self.config.get('general', {}).get('secure', True)
        self.protocol = 'https:' if self.secure else 'http:'
        self.access_key = self.config.get('s3', {}).get('access')
        self.secret_key = self.config.get('s3', {}).get('secret')
        self.http_adapter_kwargs = http_adapter_kwargs

        self.headers = default_headers()
        self.headers['User-Agent'] = self._get_user_agent_string()
        self._mount_http_adapter()

        logging_config = self.config.get('logging', {})
        if logging_config.get('level'):
            self.set_file_logger(logging_config.get('level', 'NOTSET'),
                                 logging_config.get('file', 'internetarchive.log'))
            if debug or (logger.level <= 10):
                self.set_file_logger(logging_config.get('level', 'NOTSET'),
                                     logging_config.get('file', 'internetarchive.log'),
                                     'requests.packages.urllib3')

    def _get_user_agent_string(self):
        """Generate a User-Agent string to be sent with every request."""
        uname = os.uname()
        try:
            lang = locale.getlocale()[0][:2]
        except:
            lang = ''
        py_version = '{0}.{1}.{2}'.format(*sys.version_info)
        return 'internetarchive/{0} ({1} {2}; N; {3}; {4}) Python/{5}'.format(
            __version__, uname[0], uname[-1], lang, self.access_key, py_version)

    def _mount_http_adapter(self, protocol=None, max_retries=None, status_forcelist=None):
        """Mount an HTTP adapter to the
        :class:`ArchiveSession <ArchiveSession>` object.
        """
        protocol = protocol if protocol else self.protocol
        if not max_retries:
            max_retries = self.http_adapter_kwargs.get('max_retries', 3)

        if not status_forcelist:
            status_forcelist = [500, 501, 502, 503, 504, 400, 408]
        if max_retries and isinstance(max_retries, (int, float)):
            max_retries = Retry(total=max_retries,
                                connect=max_retries,
                                read=max_retries,
                                redirect=False,
                                method_whitelist=Retry.DEFAULT_METHOD_WHITELIST,
                                status_forcelist=status_forcelist,
                                backoff_factor=1)
        self.http_adapter_kwargs['max_retries'] = max_retries
        max_retries_adapter = HTTPAdapter(**self.http_adapter_kwargs)
        # Don't mount on s3.us.archive.org, only archive.org!
        # IA-S3 requires a more complicated retry workflow.
        self.mount('{0}//archive.org'.format(self.protocol), max_retries_adapter)

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

        fh = logging.FileHandler(path)
        fh.setLevel(_log_level[log_level])

        formatter = logging.Formatter(log_format)
        fh.setFormatter(formatter)

        _log.addHandler(fh)

    def get_item(self, identifier, item_metadata=None, request_kwargs=None):
        """A method for creating :class:`internetarchive.Item <Item>` and
        :class:`internetarchive.Collection <Collection>` objects.

        :type identifier: str
        :param identifier: A globally unique Archive.org identifier.

        :type item_metadata: dict
        :param item_metadata: (optional) A metadata dict used to initialize the Item or
                              Collection object. Metadata will automatically be retrieved
                              from Archive.org if nothing is provided.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                                    :meth:`requests.sessions.Session.get` request.
        """
        request_kwargs = {} if not request_kwargs else request_kwargs
        if not item_metadata:
            logger.debug('no metadata provided for "{0}", '
                         'retrieving now.'.format(identifier))
            item_metadata = self.get_metadata(identifier, request_kwargs)
        mediatype = item_metadata.get('metadata', {}).get('mediatype')
        item_class = self.ITEM_MEDIATYPE_TABLE.get(mediatype, Item)
        return item_class(self, identifier, item_metadata)

    def get_metadata(self, identifier, request_kwargs=None):
        """Get an item's metadata from the `Metadata API
        <http://blog.archive.org/2013/07/04/metadata-api/>`__

        :type identifier: str
        :param identifier: Globally unique Archive.org identifier.

        :rtype: dict
        :returns: Metadat API response.
        """
        request_kwargs = {} if not request_kwargs else request_kwargs
        url = '{0}//archive.org/metadata/{1}'.format(self.protocol, identifier)
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 12
        try:
            resp = self.get(url, **request_kwargs)
            resp.raise_for_status()
        except Exception as exc:
            error_msg = 'Error retrieving metadata from {0}, {1}'.format(url, exc)
            logger.error(error_msg)
            raise type(exc)(error_msg)
        return resp.json()

    def search_items(self, query,
                     fields=None,
                     sorts=None,
                     params=None,
                     request_kwargs=None):
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
        request_kwargs = {} if not request_kwargs else request_kwargs
        return Search(self, query,
                      fields=fields,
                      sorts=sorts,
                      params=params,
                      request_kwargs=request_kwargs)

    def get_tasks(self,
                  identifier=None,
                  task_ids=None,
                  task_type=None,
                  params=None,
                  config=None,
                  verbose=None,
                  request_kwargs=None):
        """Get tasks from the Archive.org catalog. ``internetarchive`` must be configured
        with your logged-in-* cookies to use this function. If no arguments are provided,
        all queued tasks for the user will be returned.

        :type identifier: str
        :param identifier: (optional) The Archive.org identifier for which to retrieve
                           tasks for.

        :type task_ids: int or str
        :param task_ids: (optional) The task_ids to retrieve from the Archive.org catalog.

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
        request_kwargs = {} if not request_kwargs else request_kwargs
        _catalog = Catalog(self,
                           identifier=identifier,
                           task_ids=task_ids,
                           params=params,
                           config=config,
                           verbose=verbose,
                           request_kwargs=request_kwargs)
        if task_type:
            return eval('_catalog.{0}_rows'.format(task_type.lower()))
        else:
            return _catalog.tasks

    def s3_is_overloaded(self, identifier=None, access_key=None):
        u = '{protocol}//s3.us.archive.org'.format(protocol=self.protocol)
        p = dict(
            check_limit=1,
            accesskey=access_key,
            bucket=identifier,
        )
        r = self.get(u, params=p)
        j = r.json()
        if j.get('over_limit') == 0:
            return False
        else:
            return True
