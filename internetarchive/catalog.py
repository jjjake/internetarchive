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
internetarchive.catalog
~~~~~~~~~~~~~~~~~~~~~~~

This module contains objects for interacting with the Archive.org catalog.

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

try:
    import ujson as json
except ImportError:
    import json
from logging import getLogger
from datetime import datetime

import six
from requests.exceptions import HTTPError
import collections

from internetarchive import auth


log = getLogger(__name__)


def sort_by_date(task_dict):
    if task_dict.category == 'summary':
        return datetime.now()
    try:
        return datetime.strptime(task_dict['submittime'], '%Y-%m-%d %H:%M:%S.%f')
    except:
        return datetime.strptime(task_dict['submittime'], '%Y-%m-%d %H:%M:%S')


class Catalog(object):
    """This class represents the Archive.org catalog.
    You can use this class to access and submit tasks from the catalog.

    This is a low-level interface, and in most cases the functions
    in :mod:`internetarchive.api` and methods in
    :class:`ArchiveSession <ArchiveSession>` should be used.

    It uses the archive.org
    `Tasks API <https://archive.org/services/docs/api/tasks.html>`_

    Usage::
        >>> from internetarchive import get_session, Catalog
        >>> s = get_session()
        >>> c = Catalog(s)
        >>> tasks = c.get_tasks('nasa')
        >>> tasks[-1].task_id
        31643502
    """

    def __init__(self, archive_session, request_kwargs=None):
        """
        Initialize :class:`Catalog <Catalog>` obect.

        :type archive_session: :class:`ArchiveSession <ArchiveSession>`
        :param archive_session: An :class:`ArchiveSession <ArchiveSession>`
                                object.

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments to be used
                               in :meth:`requests.sessions.Session.get`
                               and :meth:`requests.sessions.Session.post`
                               requests.
        """
        self.session = archive_session
        self.auth = auth.S3Auth(self.session.access_key, self.session.secret_key)
        self.request_kwargs = request_kwargs if request_kwargs else dict()
        self.url = '{}//{}/services/tasks.php'.format(self.session.protocol,
                                                      self.session.host)

    def get_summary(self, identifier=None, params=None):
        """Get the total counts of catalog tasks meeting all criteria,
        organized by run status (queued, running, error, and paused).


        :type identifier: str
        :param identifier: (optional) Item identifier.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                        <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :rtype: dict
        """
        params = params if params else dict()
        if identifier:
            params['identifier'] = identifier
        params.update(dict(summary=1, history=0, catalog=0))
        r = self.make_tasks_request(params)
        j = r.json()
        if j.get('success') is True:
            return j['value']['summary']
        else:
            return j

    def make_tasks_request(self, params):
        """Make a GET request to the
         `Tasks API <https://archive.org/services/docs/api/tasks.html>`_

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :rtype: :class:`requests.Response`
        """
        r = self.session.get(self.url,
                             params=params,
                             auth=self.auth,
                             **self.request_kwargs)
        try:
            r.raise_for_status()
        except HTTPError as exc:
            j = r.json()
            error = j['error']
            raise HTTPError(error, response=r)
        return r

    def iter_tasks(self, params=None):
        """A generator that can make arbitrary requests to the
        Tasks API. It handles paging (via cursor) automatically.

        :type params: dict
        :param params: (optional) Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :rtype: collections.Iterable[CatalogTask]
        """
        while True:
            r = self.make_tasks_request(params)
            j = r.json()
            for row in j.get('value', dict()).get('catalog', list()):
                yield CatalogTask(row, self)
            for row in j.get('value', dict()).get('history', list()):
                yield CatalogTask(row, self)
            if not j.get('value', dict()).get('cursor'):
                break
            params['cursor'] = j['value']['cursor']

    def get_tasks(self, identifier=None, params=None):
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

        :rtype: List[CatalogTask]
        """
        params = params if params else dict()
        if identifier:
            params.update(dict(identifier=identifier))
        params.update(dict(limit=0))
        if not params.get('summary'):
            params['summary'] = 0
        r = self.make_tasks_request(params)
        line = ''
        tasks = list()
        for c in r.iter_content():
            if six.PY3:
                c = c.decode('utf-8')
            if c == '\n':
                j = json.loads(line)
                task = CatalogTask(j, self)
                tasks.append(task)
                line = ''
            line += c
        if line.strip():
            j = json.loads(line)
            task = CatalogTask(j, self)
            tasks.append(task)

        all_tasks = sorted(tasks, key=sort_by_date, reverse=True)
        return all_tasks

    def submit_task(self, identifier, cmd,
                    comment=None,
                    priority=None,
                    data=None,
                    headers=None):
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

        :rtype: :class:`requests.Response`
        """
        data = dict() if not data else data
        data.update(dict(cmd=cmd, identifier=identifier))
        if comment:
            if 'args' in data:
                data['args']['comment'] = comment
            else:
                data['args'] = dict(comment=comment)
        if priority:
            data['priority'] = priority
        r = self.session.post(self.url,
                              json=data,
                              auth=self.auth,
                              headers=headers,
                              **self.request_kwargs)
        return r


class CatalogTask(object):
    """This class represents an Archive.org catalog task. It is primarily used by
    :class:`Catalog`, and should not be used directly.
    """
    def __init__(self, task_dict, catalog_obj):
        self.session = catalog_obj.session
        self.request_kwargs = catalog_obj.request_kwargs
        self.color = None
        self.task_dict = task_dict
        for key, value in task_dict.items():
            setattr(self, key, value)

    def __repr__(self):
        color = self.task_dict.get('color', 'done')
        return ('CatalogTask(identifier={identifier},'
                ' task_id={task_id!r}, server={server!r},'
                ' cmd={cmd!r},'
                ' submitter={submitter!r},'
                ' color={task_color!r})'.format(task_color=color, **self.task_dict))

    def __getitem__(self, key):
        """Dict-like access provided as backward compatibility."""
        return self.task_dict[key]

    def json(self):
        return json.dumps(self.task_dict)

    def task_log(self):
        """Get task log.

        :rtype: str
        :returns: The task log as a string.

        """
        if self.task_id is None:
            raise ValueError('task_id is None')
        return self.get_task_log(self.task_id, self.session, self.request_kwargs)

    @staticmethod
    def get_task_log(task_id, session, request_kwargs=None):
        """Static method for getting a task log, given a task_id.

        This method exists so a task log can be retrieved without
        retrieving the items task history first.

        :type task_id: str or int
        :param task_id: The task id for the task log you'd like to fetch.

        :type archive_session: :class:`ArchiveSession <ArchiveSession>`

        :type request_kwargs: dict
        :param request_kwargs: (optional) Keyword arguments that
                               :py:class:`requests.Request` takes.

        :rtype: str
        :returns: The task log as a string.
        """
        request_kwargs = request_kwargs if request_kwargs else dict()
        _auth = auth.S3Auth(session.access_key, session.secret_key)
        if session.host == 'archive.org':
            host = 'catalogd.archive.org'
        else:
            host = session.host
        url = '{}//{}/services/tasks.php'.format(session.protocol, host)
        params = dict(task_log=task_id)
        r = session.get(url, params=params, auth=_auth, **request_kwargs)
        r.raise_for_status()
        return r.content.decode('utf-8', errors='surrogateescape')
