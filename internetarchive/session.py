#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2021 Internet Archive
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

:copyright: (C) 2012-2021 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import locale
import logging
import os
import platform
import sys
import warnings
from typing import Iterable, Mapping, MutableMapping
from urllib.parse import unquote, urlparse

import requests.sessions
from requests import Response
from requests.adapters import HTTPAdapter
from requests.cookies import create_cookie
from requests.utils import default_headers
from urllib3 import Retry

from internetarchive import __version__, auth, catalog
from internetarchive.config import get_config
from internetarchive.item import Collection, Item
from internetarchive.search import Search
from internetarchive.utils import parse_dict_cookies, reraise_modify

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
                 config: Mapping | None = None,
                 config_file: str = "",
                 debug: bool = False,
                 http_adapter_kwargs: MutableMapping | None = None):
        """Initialize :class:`ArchiveSession <ArchiveSession>` object with config.

        :param config: A config dict used for initializing the
                       :class:`ArchiveSession <ArchiveSession>` object.

        :param config_file: Path to config file used for initializing the
                            :class:`ArchiveSession <ArchiveSession>` object.

        :param http_adapter_kwargs: Keyword arguments used to initialize the
                                    :class:`requests.adapters.HTTPAdapter <HTTPAdapter>`
                                    object.

        :returns: :class:`ArchiveSession` object.
        """
        super().__init__()
        http_adapter_kwargs = http_adapter_kwargs or {}
        debug = bool(debug)

        self.config = get_config(config, config_file)
        self.config_file = config_file
        for ck, cv in self.config.get('cookies', {}).items():
            raw_cookie = f'{ck}={cv}'
            cookie_dict = parse_dict_cookies(raw_cookie)
            if not cookie_dict.get(ck):
                continue
            cookie = create_cookie(ck, cookie_dict[ck],
                                   domain=cookie_dict.get('domain', '.archive.org'),
                                   path=cookie_dict.get('path', '/'))
            self.cookies.set_cookie(cookie)

        self.secure: bool = self.config.get('general', {}).get('secure', True)
        self.host: str = self.config.get('general', {}).get('host', 'archive.org')
        if 'archive.org' not in self.host:
            self.host += '.archive.org'
        self.protocol = 'https:' if self.secure else 'http:'
        user_email = self.config.get('cookies', {}).get('logged-in-user')
        if user_email:
            user_email = user_email.split(';')[0]
            user_email = unquote(user_email)
        self.user_email: str = user_email
        self.access_key: str = self.config.get('s3', {}).get('access')
        self.secret_key: str = self.config.get('s3', {}).get('secret')
        self.http_adapter_kwargs: MutableMapping = http_adapter_kwargs or {}

        self.headers = default_headers()  # type: ignore[assignment]
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

    def _get_user_agent_string(self) -> str:
        """Generate a User-Agent string to be sent with every request."""
        uname = platform.uname()
        try:
            lang = locale.getlocale()[0][:2]  # type: ignore
        except Exception:
            lang = ''
        py_version = '{}.{}.{}'.format(*sys.version_info)
        return (f'internetarchive/{__version__} '
                f'({uname[0]} {uname[-1]}; N; {lang}; {self.access_key}) '
                f'Python/{py_version}')

    def rebuild_auth(self, prepared_request, response):
        """Never rebuild auth for archive.org URLs.
        """
        u = urlparse(prepared_request.url)
        if u.netloc.endswith('archive.org'):
            return
        super().rebuild_auth(prepared_request, response)

    def mount_http_adapter(self, protocol: str | None = None, max_retries: int | None = None,
                           status_forcelist: list | None = None, host: str | None = None) -> None:
        """Mount an HTTP adapter to the
        :class:`ArchiveSession <ArchiveSession>` object.

        :param protocol: HTTP protocol to mount your adapter to (e.g. 'https://').

        :param max_retries: The number of times to retry a failed request.
                            This can also be an `urllib3.Retry` object.

        :param status_forcelist: A list of status codes (as int's) to retry on.

        :param host: The host to mount your adapter to.
        """
        protocol = protocol or self.protocol
        host = host or 'archive.org'
        if max_retries is None:
            max_retries = self.http_adapter_kwargs.get('max_retries', 3)

        status_forcelist = status_forcelist or [500, 501, 502, 503, 504]
        if max_retries and isinstance(max_retries, (int, float)):
            self.http_adapter_kwargs['max_retries'] = Retry(total=max_retries,
                                connect=max_retries,
                                read=max_retries,
                                redirect=False,
                                allowed_methods=Retry.DEFAULT_ALLOWED_METHODS,
                                status_forcelist=status_forcelist,
                                backoff_factor=1)

        else:
            self.http_adapter_kwargs['max_retries'] = max_retries

        max_retries_adapter = HTTPAdapter(**self.http_adapter_kwargs)
        # Don't mount on s3.us.archive.org, only archive.org!
        # IA-S3 requires a more complicated retry workflow.
        self.mount(f'{protocol}//{host}', max_retries_adapter)

    def set_file_logger(
        self,
        log_level: str,
        path: str,
        logger_name: str = 'internetarchive'
    ) -> None:
        """Convenience function to quickly configure any level of
        logging to a file.

        :param log_level: A log level as specified in the `logging` module.

        :param path: Path to the log file. The file will be created if it doesn't already
                     exist.

        :param logger_name: The name of the logger.
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

    def get_item(self,
                 identifier: str,
                 item_metadata: Mapping | None = None,
                 request_kwargs: MutableMapping | None = None):
        """A method for creating :class:`internetarchive.Item <Item>` and
        :class:`internetarchive.Collection <Collection>` objects.

        :param identifier: A globally unique Archive.org identifier.

        :param item_metadata: A metadata dict used to initialize the Item or
                              Collection object. Metadata will automatically be retrieved
                              from Archive.org if nothing is provided.

        :param request_kwargs: Keyword arguments to be used in
                                    :meth:`requests.sessions.Session.get` request.
        """
        request_kwargs = request_kwargs or {}
        if not item_metadata:
            logger.debug(f'no metadata provided for "{identifier}", retrieving now.')
            item_metadata = self.get_metadata(identifier, request_kwargs) or {}
        mediatype = item_metadata.get('metadata', {}).get('mediatype')
        try:
            item_class = self.ITEM_MEDIATYPE_TABLE.get(mediatype, Item)
        except TypeError:
            item_class = Item
        return item_class(self, identifier, item_metadata)

    def get_metadata(self, identifier: str, request_kwargs: MutableMapping | None = None):
        """Get an item's metadata from the `Metadata API
        <http://blog.archive.org/2013/07/04/metadata-api/>`__

        :param identifier: Globally unique Archive.org identifier.

        :returns: Metadat API response.
        """
        request_kwargs = request_kwargs or {}
        url = f'{self.protocol}//{self.host}/metadata/{identifier}'
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
            error_msg = f'Error retrieving metadata from {url}, {exc}'
            logger.error(error_msg)
            raise type(exc)(error_msg)
        return resp.json()

    def search_items(self,
                     query: str,
                     fields: Iterable[str] | None = None,
                     sorts: Iterable[str] | None = None,
                     params: Mapping | None = None,
                     full_text_search: bool = False,
                     dsl_fts: bool = False,
                     request_kwargs: Mapping | None = None,
                     max_retries: int | Retry | None = None) -> Search:
        """Search for items on Archive.org.

        :param query: The Archive.org search query to yield results for. Refer to
                      https://archive.org/advancedsearch.php#raw for help formatting your
                      query.

        :param fields: The metadata fields to return in the search results.

        :param params: The URL parameters to send with each request sent to the
                       Archive.org Advancedsearch Api.

        :param full_text_search: Beta support for querying the archive.org
                                 Full Text Search API [default: False].

        :param dsl_fts: Beta support for querying the archive.org Full Text
                        Search API in dsl (i.e. do not prepend ``!L `` to the
                        ``full_text_search`` query [default: False].

        :returns: A :class:`Search` object, yielding search results.
        """
        request_kwargs = request_kwargs or {}
        return Search(self, query,
                      fields=fields,
                      sorts=sorts,
                      params=params,
                      full_text_search=full_text_search,
                      dsl_fts=dsl_fts,
                      request_kwargs=request_kwargs,
                      max_retries=max_retries)

    def s3_is_overloaded(self, identifier=None, access_key=None, request_kwargs=None):
        request_kwargs = request_kwargs or {}
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 12

        u = f'{self.protocol}//s3.us.archive.org'
        p = {
            'check_limit': 1,
            'accesskey': access_key,
            'bucket': identifier,
        }
        try:
            r = self.get(u, params=p, **request_kwargs)
        except Exception:
            return True
        try:
            j = r.json()
        except ValueError:
            return True
        return j.get('over_limit') != 0

    def get_tasks_api_rate_limit(self, cmd: str = 'derive.php', request_kwargs: dict | None = None):
        return catalog.Catalog(self, request_kwargs).get_rate_limit(cmd=cmd)

    def submit_task(self,
                    identifier: str,
                    cmd: str,
                    comment: str = '',
                    priority: int = 0,
                    data: dict | None = None,
                    headers: dict | None = None,
                    reduced_priority: bool = False,
                    request_kwargs: Mapping | None = None) -> requests.Response:
        """Submit an archive.org task.

        :param identifier: Item identifier.

        :param cmd: Task command to submit, see
                    `supported task commands
                    <https://archive.org/services/docs/api/tasks.html#supported-tasks>`_.

        :param comment: A reasonable explanation for why the
                        task is being submitted.

        :param priority: Task priority from 10 to -10
                         (default: 0).

        :param data: Extra POST data to submit with
                     the request. Refer to `Tasks API Request Entity
                     <https://archive.org/services/docs/api/tasks.html#request-entity>`_.

        :param headers: Add additional headers to request.

        :param reduced_priority: Submit your derive at a lower priority.
                                 This option is helpful to get around rate-limiting.
                                 Your task will more likely be accepted, but it might
                                 not run for a long time. Note that you still may be
                                 subject to rate-limiting. This is different than
                                 ``priority`` in that it will allow you to possibly
                                 avoid rate-limiting.

        :param request_kwargs: Keyword arguments to be used in
                               :meth:`requests.sessions.Session.post` request.

        :returns: :class:`requests.Response`
        """
        headers = headers or {}
        if reduced_priority:
            headers.update({'X-Accept-Reduced-Priority': '1'})
        return catalog.Catalog(self, request_kwargs).submit_task(identifier, cmd,
                                                         comment=comment,
                                                         priority=priority,
                                                         data=data,
                                                         headers=headers)

    def iter_history(self,
                     identifier: str | None,
                     params: dict | None = None,
                     request_kwargs: Mapping | None = None) -> Iterable[catalog.CatalogTask]:
        """A generator that returns completed tasks.

        :param identifier: Item identifier.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :param request_kwargs: Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :returns: An iterable of completed CatalogTasks.
        """
        params = params or {}
        params.update({'identifier': identifier, 'catalog': 0, 'summary': 0, 'history': 1})
        c = catalog.Catalog(self, request_kwargs)
        yield from c.iter_tasks(params)

    def iter_catalog(self,
                     identifier: str | None = None,
                     params: dict | None = None,
                     request_kwargs: Mapping | None = None) -> Iterable[catalog.CatalogTask]:
        """A generator that returns queued or running tasks.

        :param identifier: Item identifier.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :param request_kwargs: Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :returns: An iterable of queued or running CatalogTasks.
        """
        params = params or {}
        params.update({'identifier': identifier, 'catalog': 1, 'summary': 0, 'history': 0})
        c = catalog.Catalog(self, request_kwargs)
        yield from c.iter_tasks(params)

    def get_tasks_summary(self, identifier: str = "",
                          params: dict | None = None,
                          request_kwargs: Mapping | None = None) -> dict:
        """Get the total counts of catalog tasks meeting all criteria,
        organized by run status (queued, running, error, and paused).

        :param identifier: Item identifier.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :param request_kwargs: Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :returns: Counts of catalog tasks meeting all criteria.
        """
        return catalog.Catalog(self, request_kwargs).get_summary(identifier=identifier, params=params)

    def get_tasks(self, identifier: str = "",
                  params: dict | None = None,
                  request_kwargs: Mapping | None = None) -> set[catalog.CatalogTask]:
        """Get a list of all tasks meeting all criteria.
        The list is ordered by submission time.

        :param identifier: The item identifier, if provided
                           will return tasks for only this item filtered by
                           other criteria provided in params.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :param request_kwargs: Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :returns: A set of all tasks meeting all criteria.
        """
        params = params or {}
        if 'history' not in params:
            params['history'] = 1
        if 'catalog' not in params:
            params['catalog'] = 1
        return set(catalog.Catalog(self, request_kwargs).get_tasks(
            identifier=identifier,
            params=params)
        )

    def get_my_catalog(self,
                       params: dict | None = None,
                       request_kwargs: Mapping | None = None) -> set[catalog.CatalogTask]:
        """Get all queued or running tasks.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :param request_kwargs: Keyword arguments to be used in
                               :meth:`requests.sessions.Session.get` request.

        :returns: A set of all queued or running tasks.
        """
        params = params or {}
        _params = {'submitter': self.user_email, 'catalog': 1, 'history': 0, 'summary': 0}
        params.update(_params)
        return self.get_tasks(params=params, request_kwargs=request_kwargs)

    def get_task_log(self, task_id: str | int, request_kwargs: Mapping | None = None) -> str:
        """Get a task log.

        :param task_id: The task id for the task log you'd like to fetch.

        :param request_kwargs: Keyword arguments that
                               :py:class:`requests.Request` takes.

        :returns: The task log as a string.
        """
        return catalog.CatalogTask.get_task_log(task_id, self, request_kwargs)

    def send(self, request, **kwargs) -> Response:
        # Catch urllib3 warnings for HTTPS related errors.
        insecure = False
        with warnings.catch_warnings(record=True) as w:
            warnings.filterwarnings('always')
            try:
                r = super().send(request, **kwargs)
            except Exception as e:
                try:
                    reraise_modify(e, e.request.url, prepend=False)  # type: ignore
                except Exception:
                    logger.error(e)
                    raise e
            if self.protocol == 'http:':
                return r
            insecure_warnings = ['SNIMissingWarning', 'InsecurePlatformWarning']
            if w:
                for warning in w:
                    if any(x in str(warning) for x in insecure_warnings):
                        insecure = True
                        break
        if insecure:
            from requests.exceptions import RequestException
            msg = ('You are attempting to make an HTTPS request on an insecure platform,'
                   ' please see:\n\n\thttps://archive.org/services/docs/api'
                   '/internetarchive/troubleshooting.html#https-issues\n')
            raise RequestException(msg)
        return r
