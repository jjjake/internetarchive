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

import six
from six.moves.urllib.parse import parse_qsl

from internetarchive.utils import map2x


log = getLogger(__name__)


class Catalog(object):
    """This class represents the Archive.org catalog. You can use this class to access
    tasks from the catalog.

    Usage::
        >>> import internetarchive
        >>> c = internetarchive.Catalog(internetarchive.session.ArchiveSession(),
        ...                             identifier='jstor_ejc')
        >>> c.tasks[-1].task_id
        143919540
    """

    ROW_TYPES = dict(
        green=0,
        blue=1,
        red=2,
        brown=9,
        purple=-1,
    )

    def __init__(self, archive_session,
                 identifier=None,
                 task_id=None,
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

        :type task_id: int or str
        :param task_id: (optional) The task_id to retrieve from the Archive.org catalog.

        :type params: dict
        :param params: (optional) The URL parameters to send with each request sent to the
                       Archive.org catalog API.

        :type config: dict
        :param secure: (optional) Configuration options for session.

        :type verbose: bool
        :param verbose: (optional) Set to ``True`` to retrieve verbose information for
                        each catalog task returned. Verbose is set to ``True`` by default.

        """
        task_id = [] if not task_id else task_id
        params = {} if not params else params
        config = {} if not config else config
        verbose = '1' if verbose is None or verbose is True else '0'
        request_kwargs = {} if not request_kwargs else request_kwargs

        self.session = archive_session
        self.request_kwargs = request_kwargs
        # Accessing the Archive.org catalog requires a users
        # logged-in-* cookies (i.e. you must be logged in).
        # Raise an exception if they are not set.
        if not self.session.cookies.get('logged-in-user'):
            raise NameError('logged-in-user cookie not set. Use `ia configure` '
                            'to add your logged-in-user cookie to your internetarchive '
                            'config file.')
        elif not self.session.cookies.get('logged-in-sig'):
            raise NameError('logged-in-sig cookie not set. Use `ia configure` '
                            'to add your logged-in-sig cookie to your internetarchive '
                            'config file.')

        # Set cookies from config.
        self.session.cookies['verbose'] = verbose

        # Params required to retrieve JSONP from the IA catalog.
        self.params = dict(
            json=2,
            output='json',
            callback='foo',
        )
        self.params.update(params)
        # Return user's current tasks as default.
        if not identifier and not task_id and not params:
            self.params['justme'] = 1

        if task_id:
            if isinstance(task_id, list):
                task_id = task_id[0]
            task_id = str(task_id)
            self.params.update(dict(
                search_task_id=task_id,
                history=999999999999999999999,  # TODO: is there a better way?
            ))

        if identifier:
            self.url = '{0}//archive.org/history/{1}'.format(self.session.protocol,
                                                             identifier)
        elif task_id:
            self.url = '{0}//catalogd.archive.org/catalog.php'.format(
                self.session.protocol)
        else:
            self.url = '{0}//archive.org/catalog.php'.format(self.session.protocol)

        # Get tasks.
        self.tasks = self._get_tasks()

        # Set row_type attrs.
        for key in self.ROW_TYPES:
            rows = [t for t in self.tasks if t.row_type == self.ROW_TYPES[key]]
            setattr(self, '{0}_rows'.format(key), rows)

    def _get_tasks(self):
        r = self.session.get(self.url, params=self.params, **self.request_kwargs)
        content = r.content.decode('utf-8')
        # Convert JSONP to JSON (then parse the JSON).
        json_str = content[(content.index("(") + 1):content.rindex(")")]
        try:
            return [CatalogTask(t, self) for t in json.loads(json_str)]
        except ValueError:
            msg = 'Unable to parse JSON. Check your configuration and try again.'
            log.error(msg)
            raise ValueError(msg)


class CatalogTask(object):
    """This class represents an Archive.org catalog task. It is primarily used by
    :class:`Catalog`, and should not be used directly.

    """

    COLUMNS = (
        'identifier',
        'server',
        'command',
        'time',
        'submitter',
        'args',
        'task_id',
        'row_type'
    )

    def __init__(self, columns, catalog_obj):
        self.session = catalog_obj.session
        self.request_kwargs = catalog_obj.request_kwargs
        for key, value in map2x(None, self.COLUMNS, columns):
            if key:
                setattr(self, key, value)
        # special handling for 'args' - parse it into a dict if it is a string
        if isinstance(self.args, six.string_types):
            if six.PY2:
                self.args = dict(x for x in parse_qsl(self.args.encode('utf-8')))
            else:
                self.args = dict(x for x in parse_qsl(self.args))

    def __repr__(self):
        return ('CatalogTask(identifier={identifier},'
                ' task_id={task_id!r}, server={server!r},'
                ' command={command!r},'
                ' submitter={submitter!r},'
                ' row_type={row_type})'.format(**self.__dict__))

    def __getitem__(self, key):
        """Dict-like access provided as backward compatibility."""
        if key in self.COLUMNS:
            return getattr(self, key, None)
        else:
            raise KeyError(key)

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
        url = '{0}//catalogd.archive.org/log/{1}'.format(session.protocol, task_id)
        p = dict(full=1)
        r = session.get(url, params=p, **request_kwargs)
        r.raise_for_status()
        return r.content.decode('utf-8')
