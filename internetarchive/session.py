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
internetarchive.session
~~~~~~~~~~~~~~~~~~~~~~~

This module provides an ArchiveSession object to manage and persist
settings across the internetarchive package.

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals

import os
import locale
import sys
import logging
import platform
import warnings
try:
    import ujson as json
except ImportError:
    import json

import requests.sessions
from requests.utils import default_headers
from requests.adapters import HTTPAdapter
from requests.packages.urllib3 import Retry
from six.moves.urllib.parse import urlparse, unquote

from internetarchive import __version__, auth
from internetarchive.config import get_config
from internetarchive.item import Item, Collection
from internetarchive.search import Search
from internetarchive.catalog import Catalog, CatalogTask
from internetarchive.utils import reraise_modify


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
        self.config_file = config_file
        self.cookies.update(self.config.get('cookies', {}))
        self.secure = self.config.get('general', {}).get('secure', True)
        self.host = self.config.get('general', {}).get('host', 'archive.org')
        if 'archive.org' not in self.host:
            self.host += '.archive.org'
        self.protocol = 'https:' if self.secure else 'http:'
        user_email = self.config.get('cookies', dict()).get('logged-in-user')
        if user_email:
            user_email = user_email.split(';')[0]
            user_email = unquote(user_email)
        self.user_email = user_email
        self.access_key = self.config.get('s3', {}).get('access')
        self.secret_key = self.config.get('s3', {}).get('secret')
        self.http_adapter_kwargs = http_adapter_kwargs

        self.headers = default_headers()
        self.headers.update({'User-Agent': self._get_user_agent_string()})
        self.headers.update({'Connection': 'close'})

        self.mount_http_adapter()

        logging_config = self.config.get('logging', {})
        if logging_config.get('level'):
            self.set_file_logger(logging_config.get('level', 'NOTSET'),
                                 logging_config.get('file', 'internetarchive.log'))
            if debug or (logger.level <= 10):
                self.set_file_logger(logging_config.get('level', 'NOTSET'),
                                     logging_config.get('file', 'internetarchive.log'),
                                     'urllib3')

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

    def rebuild_auth(self, prepared_request, response):
        """Never rebuild auth for archive.org URLs.
        """
        u = urlparse(prepared_request.url)
        if u.netloc.endswith('archive.org'):
            return
        super(ArchiveSession, self).rebuild_auth(prepared_request, response)

    def mount_http_adapter(self, protocol=None, max_retries=None,
                           status_forcelist=None, host=None):
        """Mount an HTTP adapter to the
        :class:`ArchiveSession <ArchiveSession>` object.

        :type protocol: str
        :param protocol: HTTP protocol to mount your adapter to (e.g. 'https://').

        :type max_retries: int, object
        :param max_retries: The number of times to retry a failed request.
                            This can also be an `urllib3.Retry` object.

        :type status_forcelist: list
        :param status_forcelist: A list of status codes (as int's) to retry on.

        :type host: str
        :param host: The host to mount your adapter to.
        """
        protocol = protocol if protocol else self.protocol
        host = host if host else 'archive.org'
        if max_retries is None:
            max_retries = self.http_adapter_kwargs.get('max_retries', 3)

        if not status_forcelist:
            status_forcelist = [500, 501, 502, 503, 504]
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
        self.mount('{0}//{1}'.format(protocol, host), max_retries_adapter)

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
        try:
            item_class = self.ITEM_MEDIATYPE_TABLE.get(mediatype, Item)
        except TypeError:
            item_class = Item
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
        url = '{0}//{1}/metadata/{2}'.format(self.protocol, self.host, identifier)
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 12
        try:
            if self.access_key and self.secret_key:
                s3_auth = auth.S3Auth(self.access_key, self.secret_key)
            else:
                s3_auth = None
            resp = self.get(url, auth=s3_auth, **request_kwargs)
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
                     request_kwargs=None,
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
        request_kwargs = {} if not request_kwargs else request_kwargs
        return Search(self, query,
                      fields=fields,
                      sorts=sorts,
                      params=params,
                      request_kwargs=request_kwargs,
                      max_retries=max_retries)

    def s3_is_overloaded(self, identifier=None, access_key=None, request_kwargs=None):
        request_kwargs = {} if not request_kwargs else request_kwargs
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 12

        u = '{protocol}//s3.us.archive.org'.format(protocol=self.protocol)
        p = dict(
            check_limit=1,
            accesskey=access_key,
            bucket=identifier,
        )
        try:
            r = self.get(u, params=p, **request_kwargs)
        except:
            return True
        try:
            j = r.json()
        except ValueError:
            return True
        if j.get('over_limit') == 0:
            return False
        else:
            return True

    def submit_task(self, identifier, cmd, comment=None, priority=None, data=None,
                    headers=None, reduced_priority=None, request_kwargs=None):
        """Submit an archive.org task.

        :type identifier: str
        :param identifier: Item identifier.

        :type cmd: str
        :param cmd: Task command to submit, see
                    `supported task commands
                    <https://archive.org/services/docs/api/tasks.html#supported-tasks>`_.

        :type comment: str
        :param comment: (optional) A reasonable explanation for why the
                        task is being submitted.

        :type priority: int
        :param priority: (optional) Task priority from 10 to -10
                         (default: 0).

        :type data: dict
        :param data: (optional) Extra POST data to submit with
                     the request. Refer to `Tasks API Request Entity
                     <https://archive.org/services/docs/api/tasks.html#request-entity>`_.

        :type headers: dict
        :param headers: (optional) Add additional headers to request.

        :type reduced_priority: bool
        :param reduced_priority: (optional) Submit your derive at a lower priority.
                                 This option is helpful to get around rate-limiting.
                                 Your task will more likey be accepted, but it might
                                 not run for a long time. Note that you still may be
                                 subject to rate-limiting. This is different than
                                 ``priority`` in that it will allow you to possibly
                                 avoid rate-limiting.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                               :meth:`requests.sessions.Session.post` request.

        :rtype: :class:`requests.Response`
        """
        headers = dict() if not headers else headers
        if reduced_priority is not None:
            headers.update({'X-Accept-Reduced-Priority': '1'})

        c = Catalog(self, request_kwargs)
        r = c.submit_task(identifier, cmd,
                          comment=comment,
                          priority=priority,
                          data=data,
                          headers=headers)
        return r

    def iter_history(self, identifier, params=None, request_kwargs=None):
        """A generator that returns completed tasks.

        :type identifier: str
        :param identifier: (optional) Item identifier.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :rtype: collections.Iterable[CatalogTask]
        """
        params = dict() if not params else params
        params.update(dict(identifier=identifier, catalog=0, summary=0, history=1))
        c = Catalog(self, request_kwargs)
        for j in c.iter_tasks(params):
            yield j

    def iter_catalog(self, identifier=None, params=None, request_kwargs=None):
        """A generator that returns queued or running tasks.

        :type identifier: str
        :param identifier: (optional) Item identifier.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :rtype: collections.Iterable[CatalogTask]
        """
        params = dict() if not params else params
        params.update(dict(identifier=identifier, catalog=1, summary=0, history=0))
        c = Catalog(self, request_kwargs)
        for j in c.iter_tasks(params):
            yield j

    def get_tasks_summary(self, identifier=None, params=None, request_kwargs=None):
        """Get the total counts of catalog tasks meeting all criteria,
        organized by run status (queued, running, error, and paused).

        :type identifier: str
        :param identifier: (optional) Item identifier.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :rtype: dict
        """
        c = Catalog(self, request_kwargs)
        return c.get_summary(identifier=identifier, params=params)

    def get_tasks(self, identifier=None, params=None, request_kwargs=None):
        """Get a list of all tasks meeting all criteria.
        The list is ordered by submission time.

        :type identifier: str
        :param identifier: (optional) The item identifier, if provided
                           will return tasks for only this item filtered by
                           other criteria provided in params.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :rtype: List[CatalogTask]
        """
        params = dict() if not params else params
        c = Catalog(self, request_kwargs)
        if 'history' not in params:
            params['history'] = 1
        if 'catalog' not in params:
            params['catalog'] = 1
        return c.get_tasks(identifier=identifier, params=params)

    def get_my_catalog(self, params=None, request_kwargs=None):
        """Get all queued or running tasks.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :rtype: List[CatalogTask]
        """
        params = dict() if not params else params
        _params = dict(submitter=self.user_email, catalog=1, history=0, summary=0)
        params.update(_params)
        return self.get_tasks(params=params, request_kwargs=request_kwargs)

    def get_task_log(self, task_id, request_kwargs=None):
        """Get a task log.

        :type task_id: str or int
        :param task_id: The task id for the task log you'd like to fetch.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments that
                               :py:class:`requests.Request` takes.

        :rtype: str
        :returns: The task log as a string.
        """
        return CatalogTask.get_task_log(task_id, self, request_kwargs)

    def send(self, request, **kwargs):
        # Catch urllib3 warnings for HTTPS related errors.
        insecure = False
        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings('always')
            try:
                r = super(ArchiveSession, self).send(request, **kwargs)
            except Exception as e:
                try:
                    reraise_modify(e, e.request.url, prepend=False)
                except:
                    logger.error(e)
                    raise e
            if self.protocol == 'http:':
                return r
            insecure_warnings = ['SNIMissingWarning', 'InsecurePlatformWarning']
            if w:
                for e in w:
                    if any(x in str(e) for x in insecure_warnings):
                        insecure = True
                        break
        if insecure:
            from requests.exceptions import RequestException
            msg = ('You are attempting to make an HTTPS request on an insecure platform,'
                   ' please see:\n\n\thttps://archive.org/services/docs/api'
                   '/internetarchive/troubleshooting.html#https-issues\n')
            raise RequestException(msg)
        return r
