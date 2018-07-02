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
from copy import copy
from time import sleep

from six.moves import urllib_parse
import pycurl

from internetarchive.config import get_config
from internetarchive.item import Item, Collection
from internetarchive.catalog import Catalog
from internetarchive import __version__
from internetarchive.models import ArchiveRequest, ArchiveResponse
from internetarchive.search import Search
from internetarchive.exceptions import AuthenticationError


logger = logging.getLogger(__name__)

## TODO: delete this block.
#ch = logging.StreamHandler()
#ch.setLevel(logging.DEBUG)
#logger.addHandler(ch)


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
                 headers=None,
                 verbose=None,
                 debug_callback=None):
        """Initialize :class:`ArchiveSession <ArchiveSession>` object with config.

        :type config: dict
        :param config: (optional) A config dict used for initializing the
                       :class:`ArchiveSession <ArchiveSession>` object.

        :type config_file: str
        :param config_file: (optional) Path to config file used for initializing the
                            :class:`ArchiveSession <ArchiveSession>` object.

        :type headers: dict
        :param headers: (optional) HTTP headers to add to every request.

        :type verbose: bool
        :param verbose: (optional) Toggle pycurl verbosity on or off.

        :returns: :class:`ArchiveSession` object.
        """
        headers = dict() if not headers else headers

        self.config = get_config(config, config_file)
        self.config_file = config_file
        self.cookies = self.config.get('cookies', {})
        self.secure = self.config.get('general', {}).get('secure', True)
        self.protocol = 'https:' if self.secure else 'http:'
        self.host = self.config.get('general', {}).get('host', 'archive.org')
        self.access_key = self.config.get('s3', {}).get('access')
        self.secret_key = self.config.get('s3', {}).get('secret')
        self.verbose = verbose
        self.debug_callback = debug_callback

        self.headers = self._default_headers()
        self.headers.update(headers)

        self.curl_instance = pycurl.Curl()
        self.curl_instance.setopt(self.curl_instance.USERAGENT,
                                  self._get_user_agent_string())

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
        h = {
                'Authorization': 'LOW {0}:{1}'.format(self.access_key, self.secret_key),
                'User-Agent': self._get_user_agent_string(),
        }
        return h

    def make_url(self, path=None, host=None):
        host = self.host if host is None else host
        if path:
            path = path.lstrip('/')
            url = '{}//{}/{}'.format(self.protocol, host, path)
        else:
            url = '{}//{}'.format(self.protocol, host, path)
        return url

    def _request(self, method, url,
                 params=None, data=None, headers=None, cookies=None, output_file=None,
                 retries=None, timeout=None, connect_timeout=None, input_file_obj=None):
        headers = headers if headers else dict()
        data = data if data else dict()
        _headers = copy(self.headers)
        _headers.update(headers)

        cookies = {'test-cookie': '1'}
        self.prepare_cookies(cookies)

        req = ArchiveRequest(
                curl_instance=self.curl_instance,
                method=method.upper(),
                url=url,
                data=data,
                params=params,
                headers=_headers,
                output_file=output_file,
                input_file_obj=input_file_obj,
                access_key=self.access_key,
                secret_key=self.secret_key,
                verbose=self.verbose,
                timeout=timeout,
                connect_timeout=connect_timeout,
        )

        if self.debug_callback:
            self.curl_instance.setopt(pycurl.DEBUGFUNCTION, self.debug_callback)

        r = self.send(req, retries=retries)
        return r

    def prepare_cookies(self, cookies):
        cookie_str = ('logged-in-user={logged-in-user};'
                      'logged-in-sig={logged-in-sig};').format(**self.cookies)
        for k in cookies:
            cookie_str += '{0}={1};'.format(k, cookies[k])
        cookie_str = cookie_str.strip(';')
        self.curl_instance.setopt(self.curl_instance.COOKIE, cookie_str)

    def send(self, request, retries=None, status_forcelist=None):
        if not status_forcelist:
            status_forcelist = [500, 501, 502, 503, 504]
        retries = 3 if retries is None else retries

        response = ArchiveResponse(request)
        self.curl_instance.setopt(self.curl_instance.HEADERFUNCTION,
                                  response.header_function)

        tries = 0
        backoff = 2
        while True:
            tries += 1
            if tries > retries:
                break

            sleep_time = (tries*backoff)
            try:
                self.curl_instance.perform()
                status_code = self.curl_instance.getinfo(self.curl_instance.RESPONSE_CODE)
                response.status_code = status_code
                break
            except pycurl.error as exc:
                logger.error(exc)
                if tries < retries:
                    # TODO: improve retry msg.
                    logger.warning('Retrying')
                    continue
                else:
                    exit_code, msg = exc.args
                    raise(exc)

            if status_code in status_forcelist:
                # TODO: improve retry msg.
                logger.warning('Retrying')
                sleep(sleep_time)
                continue

        # Reset curl instance after each request.
        self.curl_instance.reset()

        return response

    def get(self, url, **request_kwargs):
        return self._request('GET', url, **request_kwargs)

    def post(self, url, **request_kwargs):
        return self._request('POST', url, **request_kwargs)

    def put(self, url, **request_kwargs):
        return self._request('PUT', url, **request_kwargs)

    def delete(self, url, **request_kwargs):
        return self._request('DELETE', url, **request_kwargs)

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

    def get_item(self, identifier, **request_kwargs):
        """A method for creating :class:`internetarchive.Item <Item>` and
        :class:`internetarchive.Collection <Collection>` objects.

        :type identifier: str
        :param identifier: A globally unique Archive.org identifier.
        """
        url = self.make_url('/metadata/{}'.format(identifier))
        r = self.get(url, **request_kwargs)
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
                     max_retries=None,
                     timeout=None):
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
        return Search(self, query,
                      fields=fields,
                      sorts=sorts,
                      params=params,
                      max_retries=max_retries,
                      timeout=timeout)

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
        """Check to see if S3 is overloaded.

        :type identifier: str
        :param identifier: (optional) If provided, check to see if a specific item is
                           being rate-limited.

        :returns: ``True`` if S3 is overloaded, otherwise ``False``.
        """
        p = dict(
            check_limit=1,
            accesskey=self.access_key,
            bucket=identifier,
        )
        url = self.make_url(host='s3.us.archive.org')
        try:
            r = self.get(url, params=p)
            if r.json.get('over_limit') == 0:
                return False
        except Exception as exc:
            pass
        return True

    def get_auth_config(self, username, password):
        """Get your archive.org credentials given your username and password.

        :type username: str
        :param username: The email address associated with your archive.org account.

        :type password: str
        :param password: Your archive.org password.

        :returns: A dict containing your logged-in-* cookies, IA-S3 keys, and screenname.
        """
        # logged-in-* cookies.
        payload = dict(
            username=username,
            password=password,
            remember='CHECKED',
            action='login',
            submit='Log in',
        )
        url = self.make_url('account/login.php')
        r = self.post(url, data=payload)
        cookies = r.headers['set-cookie']
        if not any(['logged-in-' in x for x in cookies]):
            raise AuthenticationError('Authentication failed. '
                                      'Please check your credentials and try again.')
        auth_config = dict(s3=dict(), cookies=dict())
        for c in cookies:
            if 'logged-in' in c:
                k, v = c.split('=', 1)
                v = v.split(';')[0]
                auth_config['cookies'][k] = v

        # S3 Keys.
        url = self.make_url('/account/s3.php')
        p = dict(output_json=1)
        r = self.get(url, params=p)
        j = r.json
        if not j or not j.get('key'):
            raise AuthenticationError('Authorization failed. Please check your '
                                      'credentials and try again.')
        auth_config['s3']['access'] = j['key']['s3accesskey']
        auth_config['s3']['secret'] = j['key']['s3secretkey']

        # Screenname.
        url = self.make_url(host='s3.us.archive.org')
        p = dict(check_auth=1)
        r = self.get(url, params=p)
        if r.json.get('error'):
            raise AuthenticationError(r.json.get('error'))
        auth_config['general'] = dict(screenname=r.json['screenname'])

        return auth_config
