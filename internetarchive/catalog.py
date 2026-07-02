#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2026 Internet Archive
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

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from datetime import datetime
from logging import getLogger

import requests
from requests import Response
from requests.exceptions import HTTPError

from internetarchive import auth
from internetarchive import session as ia_session
from internetarchive.utils import json

log = getLogger(__name__)

FOLLOW_POLL_INTERVAL = 2.0

# How many consecutive transient request failures follow mode tolerates
# before re-raising (failures 1 through N-1 are retried; the Nth is fatal).
# Each counted failure already represents an exhausted session-layer urllib3
# retry cycle, so reaching this means a genuinely persistent outage.
FOLLOW_MAX_CONSECUTIVE_ERRORS = 5

# Task ``status`` values that mean the task is still alive and may produce more
# log output. A finished task is either done (returned from history with a null
# status) or errored (``status='error'``, which lingers in the catalog awaiting
# admin) -- both are terminal for follow purposes.
ACTIVE_TASK_STATUSES = frozenset({'running', 'queued', 'paused'})


def _is_transient_error(exc: requests.exceptions.RequestException) -> bool:
    """Return ``True`` if ``exc`` is a transient failure worth retrying.

    Connection errors, premature chunked responses, timeouts, and 5xx
    responses are transient. 4xx responses (and an ``HTTPError`` without an
    attached response) are fatal -- they won't heal by retrying.

    :param exc: The exception raised by a follow-mode request.

    :returns: ``True`` if the error is transient, else ``False``.
    """
    if isinstance(exc, HTTPError):
        return exc.response is not None and exc.response.status_code >= 500
    return isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.Timeout,
        ),
    )


def sort_by_date(task_dict: CatalogTask) -> datetime:
    if task_dict.category == 'summary':  # type: ignore
        return datetime.now()
    try:
        return datetime.strptime(task_dict['submittime'], '%Y-%m-%d %H:%M:%S.%f')
    except Exception:
        return datetime.strptime(task_dict['submittime'], '%Y-%m-%d %H:%M:%S')


class Catalog:
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

    def __init__(
        self,
        archive_session: ia_session.ArchiveSession,
        request_kwargs: Mapping | None = None,
    ):
        """
        Initialize :class:`Catalog <Catalog>` object.

        :param archive_session: An :class:`ArchiveSession <ArchiveSession>`
                                object.

        :param request_kwargs: Keyword arguments to be used
                               in :meth:`requests.sessions.Session.get`
                               and :meth:`requests.sessions.Session.post`
                               requests.
        """
        self.session = archive_session
        self.auth = auth.S3Auth(self.session.access_key, self.session.secret_key)
        self.request_kwargs = request_kwargs or {}
        self.url = f'{self.session.protocol}//{self.session.host}/services/tasks.php'

    def get_summary(self, identifier: str = "", params: dict | None = None) -> dict:
        """Get the total counts of catalog tasks meeting all criteria,
        organized by run status (queued, running, error, and paused).


        :param identifier: Item identifier.

        :param params: Query parameters, refer to

        `Tasks API <https://archive.org/services/docs/api/tasks.html>`_
        for available parameters.

        :returns: the total counts of catalog tasks meeting all criteria
        """
        params = params or {}
        if identifier:
            params['identifier'] = identifier
        params.update({'summary': 1, 'history': 0, 'catalog': 0})
        r = self.make_tasks_request(params)
        j = r.json()
        if j.get('success') is True:
            return j['value']['summary']
        else:
            return j

    def make_tasks_request(self, params: Mapping | None) -> Response:
        """Make a GET request to the
         `Tasks API <https://archive.org/services/docs/api/tasks.html>`_

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :returns: :class:`requests.Response`
        """
        r = self.session.get(
            self.url, params=params, auth=self.auth, **self.request_kwargs
        )
        try:
            r.raise_for_status()
        except HTTPError as exc:
            j = r.json()
            error = j['error']
            raise HTTPError(error, response=r)
        return r

    def iter_tasks(self, params: MutableMapping | None = None) -> Iterable[CatalogTask]:
        """A generator that can make arbitrary requests to the
        Tasks API. It handles paging (via cursor) automatically.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :returns: collections.Iterable[CatalogTask]
        """
        params = params or {}
        while True:
            r = self.make_tasks_request(params)
            j = r.json()
            for row in j.get('value', {}).get('catalog', []):
                yield CatalogTask(row, self)
            for row in j.get('value', {}).get('history', []):
                yield CatalogTask(row, self)
            if not j.get('value', {}).get('cursor'):
                break
            params['cursor'] = j['value']['cursor']

    def get_rate_limit(self, cmd: str = 'derive.php') -> dict:
        """Get the current rate limit status for a task command.

        :param cmd: The task command to check (e.g., ``'derive.php'``).

        :returns: A dict containing rate limit information.
        """
        params = {'rate_limits': 1, 'cmd': cmd}
        r = self.make_tasks_request(params)
        line = ''
        tasks = []
        for c in r.iter_content():
            c = c.decode('utf-8')
            if c == '\n':
                j = json.loads(line)
                task = CatalogTask(j, self)
                tasks.append(task)
                line = ''
            line += c
        j = json.loads(line)
        return j

    def get_tasks(
        self, identifier: str = "", params: dict | None = None
    ) -> list[CatalogTask]:
        """Get a list of all tasks meeting all criteria.
        The list is ordered by submission time.

        :param identifier: The item identifier, if provided
                           will return tasks for only this item filtered by
                           other criteria provided in params.

        :param params: Query parameters, refer to

        `Tasks API <https://archive.org/services/docs/api/tasks.html>`_
        for available parameters.

        :returns: A list of all tasks meeting all criteria.
        """
        params = params or {}
        if identifier:
            params.update({'identifier': identifier})
        params.update({'limit': 0})
        if not params.get('summary'):
            params['summary'] = 0
        r = self.make_tasks_request(params)
        line = ''
        tasks = []
        for c in r.iter_content():
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

    def submit_task(
        self,
        identifier: str,
        cmd: str,
        comment: str | None = None,
        priority: int = 0,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Response:
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

        :returns: :class:`requests.Response`
        """
        data = data or {}
        data.update({'cmd': cmd, 'identifier': identifier})
        if comment:
            if 'args' in data:
                data['args']['comment'] = comment
            else:
                data['args'] = {'comment': comment}
        if priority:
            data['priority'] = priority
        r = self.session.post(
            self.url, json=data, auth=self.auth, headers=headers, **self.request_kwargs
        )
        return r


class CatalogTask:
    """This class represents an Archive.org catalog task. It is primarily used by
    :class:`Catalog`, and should not be used directly.
    """

    def __init__(self, task_dict: Mapping, catalog_obj: Catalog):
        self.session = catalog_obj.session
        self.request_kwargs = catalog_obj.request_kwargs
        self.color = None
        self.task_dict = task_dict
        for key, value in task_dict.items():
            setattr(self, key, value)  # Confuses mypy ;-)

    def __repr__(self):
        color = self.task_dict.get('color', 'done')
        return (
            'CatalogTask(identifier={identifier},'
            ' task_id={task_id!r}, server={server!r},'
            ' cmd={cmd!r},'
            ' submitter={submitter!r},'
            ' color={task_color!r})'.format(task_color=color, **self.task_dict)
        )

    def __getitem__(self, key: str):
        """Dict-like access provided as backward compatibility."""
        return self.task_dict[key]

    def json(self):
        return json.dumps(self.task_dict)

    def task_log(self) -> str:
        """Get task log.

        :returns: The task log as a string.

        """
        task_id = self.task_id  # type: ignore
        if task_id is None:
            raise ValueError('task_id is None')
        return self.get_task_log(
            task_id, self.session, request_kwargs=self.request_kwargs
        )

    @staticmethod
    def _request_task_log(
        task_id: int | str | None,
        session: ia_session.ArchiveSession,
        *,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> Response:
        """Make the HTTP request for a task log and return the raw Response.

        :param task_id: The task id for the task log you'd like to fetch.

        :param session: :class:`ArchiveSession <ArchiveSession>`

        :param params: Extra URL parameters to send with the request.

        :param request_kwargs: Keyword arguments that
                               :py:class:`requests.Request` takes.

        :returns: :class:`requests.Response`
        """
        request_kwargs = request_kwargs or {}
        _auth = auth.S3Auth(session.access_key, session.secret_key)
        if session.host == 'archive.org':
            host = 'catalogd.archive.org'
        else:
            host = session.host
        url = f'{session.protocol}//{host}/services/tasks.php'
        _params = {'task_log': task_id}
        if params:
            _params.update(params)
        r = session.get(url, params=_params, auth=_auth, **request_kwargs)
        r.raise_for_status()
        return r

    @staticmethod
    def get_task_log(
        task_id: int | str | None,
        session: ia_session.ArchiveSession,
        *,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> str:
        """Static method for getting a task log, given a task_id.

        This method exists so a task log can be retrieved without
        retrieving the items task history first.

        :param task_id: The task id for the task log you'd like to fetch.

        :param session: :class:`ArchiveSession <ArchiveSession>`

        :param params: URL parameters to send with the request (e.g.
                       ``{'lines': 100}`` to fetch a truncated log).

        :param request_kwargs: Keyword arguments that
                               :py:class:`requests.Request` takes.

        :returns: The task log as a string.
        """
        r = CatalogTask._request_task_log(
            task_id, session, params=params, request_kwargs=request_kwargs
        )
        return r.content.decode('utf-8', errors='surrogateescape')

    @staticmethod
    def _select_log_lines(text: str, lines: int | None) -> str:
        """Return the initial backlog slice of ``text`` for follow mode.

        Replicates Tasks API ``lines`` semantics: ``None`` -> whole log,
        negative ``N`` -> last N lines, ``0`` -> nothing. Positive values
        (first N lines / the head of the log) are rejected by the callers,
        since a head slice cannot be followed.

        :param text: The full decoded task log.

        :param lines: Number of lines of backlog to keep, or ``None`` for all.

        :returns: The selected backlog text (newlines preserved).
        """
        if lines is None:
            return text
        if lines == 0:
            return ''
        parts = text.splitlines(keepends=True)
        selected = parts[:lines] if lines > 0 else parts[lines:]
        return ''.join(selected)

    @staticmethod
    def _task_is_active(
        task_id: int | str,
        session: ia_session.ArchiveSession,
        request_kwargs: Mapping | None = None,
    ) -> bool:
        """Return ``True`` while the task may still produce log output.

        A task's ``status`` is the authoritative signal: ``running``,
        ``queued`` and ``paused`` are alive, while ``error`` (which lingers in
        the catalog awaiting admin) and ``done`` (returned from history with a
        null status) are terminal. Catalog membership alone is not reliable.

        :param task_id: The task id to check.

        :param session: :class:`ArchiveSession <ArchiveSession>`

        :param request_kwargs: Keyword arguments for the request.

        :returns: ``True`` if the task is active, else ``False``.
        """
        tasks = session.get_tasks(
            params={'task_id': task_id, 'catalog': 1, 'history': 1, 'summary': 0},
            request_kwargs=request_kwargs,
        )
        for t in tasks:
            if str(getattr(t, 'task_id', '')) == str(task_id):
                if getattr(t, 'status', None) in ACTIVE_TASK_STATUSES:
                    return True
        return False

    @staticmethod
    def follow_task_log(
        task_id: int | str,
        session: ia_session.ArchiveSession,
        *,
        lines: int | None = None,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> Iterator[str]:
        """Follow a task log as it grows, ``tail -f`` style.

        Yields newly appended text as it appears. Stops automatically when
        the task's status indicates it has finished (the task is no longer
        ``running``, ``queued``, or ``paused``).

        :param task_id: The task id to follow.

        :param session: :class:`ArchiveSession <ArchiveSession>`

        :param lines: How much existing backlog to emit before following,
                      using Tasks API ``lines`` semantics: ``None`` = the
                      whole log, negative ``N`` = the last ``N`` lines, ``0`` =
                      none. A positive value (the head of the log) cannot be
                      followed and is rejected.

        :param params: Extra URL parameters forwarded to every task-log
                       request. Do not pass the Tasks API ``lines`` parameter
                       here (it would truncate the body and break delta
                       tracking) -- use the ``lines`` argument instead.

        :param request_kwargs: Keyword arguments that
                               :py:class:`requests.Request` takes.

        :returns: An iterator of newly appended log text.

        :raises ValueError: If ``lines`` is positive (the head of the log
            cannot be followed; use a negative value for the last N lines).

        :raises requests.exceptions.RequestException: On a fatal request
            error, or when transient errors persist for
            ``FOLLOW_MAX_CONSECUTIVE_ERRORS`` consecutive polls.
        """
        if lines is not None and lines > 0:
            raise ValueError(
                "follow_task_log: a positive 'lines' value selects the head "
                "of the log and cannot be followed; use a negative value for "
                "the last N lines (e.g. lines=-20)"
            )
        seen = 0
        last_modified = None
        first = True
        consecutive_errors = 0

        def _request_kwargs(conditional: bool) -> dict:
            # The conditional poll sends If-Modified-Since for a cheap 304;
            # the final/unconditional read must never be short-circuited by a
            # conditional header (including one a caller supplied), or it could
            # 304 away the trailing bytes it exists to catch.
            rk = dict(request_kwargs or {})
            headers = dict(rk.get('headers', {}))
            if conditional and last_modified:
                headers['If-Modified-Since'] = last_modified
            else:
                headers.pop('If-Modified-Since', None)
            rk['headers'] = headers
            return rk

        while True:
            # Everything is computed inside the try and yielded outside it,
            # so a failure can never lose or duplicate already-fetched
            # output, and exceptions never fire mid-yield.
            to_yield: list[str] = []
            stop = False
            try:
                checked_first = first
                r = CatalogTask._request_task_log(
                    task_id,
                    session,
                    params=params,
                    request_kwargs=_request_kwargs(conditional=True),
                )

                grew = False
                if r.status_code != 304:
                    body = r.content.decode('utf-8', errors='surrogateescape')
                    lm = r.headers.get('Last-Modified')
                    if lm:
                        last_modified = lm
                    # Task logs are append-only in practice; a body shorter
                    # than what we've already emitted can only be a transient
                    # bad response, so such a poll is skipped entirely.
                    if first:
                        initial = CatalogTask._select_log_lines(body, lines)
                        if initial:
                            to_yield.append(initial)
                        seen = len(body)
                        first = False
                        grew = True
                    elif len(body) >= seen:
                        new = body[seen:]
                        if new:
                            to_yield.append(new)
                            seen = len(body)
                            grew = True

                # Check the task status after the first poll (so an already
                # finished task exits at once instead of waiting a full poll
                # interval) and on any later poll that produced no new output.
                terminal = False
                if checked_first or not grew:
                    terminal = not CatalogTask._task_is_active(
                        task_id, session, request_kwargs=request_kwargs
                    )
                # Only fetch the trailing bytes when this poll produced nothing,
                # so a failed final fetch can never discard buffered output.
                if terminal and not grew:
                    r = CatalogTask._request_task_log(
                        task_id,
                        session,
                        params=params,
                        request_kwargs=_request_kwargs(conditional=False),
                    )
                    body = r.content.decode('utf-8', errors='surrogateescape')
                    if len(body) >= seen:
                        new = body[seen:]
                        if new:
                            to_yield.append(new)
                    stop = True
            except requests.exceptions.RequestException as exc:
                if not _is_transient_error(exc):
                    raise
                consecutive_errors += 1
                if consecutive_errors >= FOLLOW_MAX_CONSECUTIVE_ERRORS:
                    raise
                log.warning(
                    'Transient error following task %s log (%d/%d): %s',
                    task_id,
                    consecutive_errors,
                    FOLLOW_MAX_CONSECUTIVE_ERRORS,
                    exc,
                )
                time.sleep(FOLLOW_POLL_INTERVAL)
                continue
            consecutive_errors = 0
            yield from to_yield
            if stop:
                return
            # A terminal task that just emitted its backlog reconciles on the
            # next poll without sleeping first -- no idle wait before exit.
            if not terminal:
                time.sleep(FOLLOW_POLL_INTERVAL)
