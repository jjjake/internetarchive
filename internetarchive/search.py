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
internetarchive.search
~~~~~~~~~~~~~~~~~~~~~~

This module provides objects for interacting with the Archive.org
search engine.

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals

import itertools
from logging import getLogger

import six

from internetarchive.auth import S3Auth


log = getLogger(__name__)


class Search(object):
    """This class represents an archive.org item search. You can use
    this class to search for Archive.org items using the advanced search
    engine.

    Usage::

        >>> from internetarchive.session import ArchiveSession
        >>> from internetarchive.search import Search
        >>> s = ArchiveSession()
        >>> search = Search(s, '(uploader:jake@archive.org)')
        >>> for result in search:
        ...     print(result['identifier'])
    """

    def __init__(self, archive_session, query,
                 fields=None,
                 sorts=None,
                 params=None,
                 request_kwargs=None,
                 max_retries=None):
        params = params or {}

        self.session = archive_session
        self.query = query
        self.fields = fields or list()
        self.sorts = sorts or list()
        self.request_kwargs = request_kwargs or dict()
        self._num_found = None
        self.scrape_url = '{0}//{1}/services/search/v1/scrape'.format(
            self.session.protocol, self.session.host)
        self.search_url = '{0}//{1}/advancedsearch.php'.format(
            self.session.protocol, self.session.host)
        if self.session.access_key and self.session.secret_key:
            self.auth = S3Auth(self.session.access_key, self.session.secret_key)
        else:
            self.auth = None
        self.max_retries = max_retries if max_retries is not None else 5

        # Initialize params.
        default_params = dict(q=query)
        if 'page' not in params:
            default_params['count'] = 10000
        else:
            default_params['output'] = 'json'
        # In the beta endpoint 'scope' was called 'index'.
        # Let's support both for a while.
        if 'index' in params:
            params['scope'] = params['index']
            del params['index']
        self.params = default_params.copy()
        self.params.update(params)

        # Set timeout.
        if 'timeout' not in self.request_kwargs:
            self.request_kwargs['timeout'] = 300

        # Set retries.
        self.session.mount_http_adapter(max_retries=self.max_retries)

    def __repr__(self):
        return 'Search(query={query!r})'.format(query=self.query)

    def __iter__(self):
        return self.iter_as_results()

    def _advanced_search(self):
        # Always return identifier.
        if 'identifier' not in self.fields:
            self.fields.append('identifier')
        for k, v in enumerate(self.fields):
            key = 'fl[{0}]'.format(k)
            self.params[key] = v

        for i, field in enumerate(self.sorts):
            self.params['sort[{0}]'.format(i)] = field

        self.params['output'] = 'json'

        r = self.session.get(self.search_url, params=self.params, **self.request_kwargs)
        j = r.json()
        for item in j.get('response', {}).get('docs', []):
            yield item

    def _scrape(self):
        if self.fields:
            self.params['fields'] = ','.join(self.fields)
        if self.sorts:
            self.params['sorts'] = ','.join(self.sorts)
        while True:
            r = self.session.post(self.scrape_url,
                                  params=self.params,
                                  auth=self.auth,
                                  **self.request_kwargs)
            j = r.json()
            self._handle_scrape_error(j)

            self.params['cursor'] = j.get('cursor')
            for item in j['items']:
                yield item
            if 'cursor' not in j:
                break

    def _make_results_generator(self):
        if 'page' in self.params:
            return self._advanced_search()
        else:
            return self._scrape()

    @property
    def num_found(self):
        if not self._num_found:
            p = self.params.copy()
            p['total_only'] = 'true'
            r = self.session.post(self.scrape_url,
                                  params=p,
                                  auth=self.auth,
                                  **self.request_kwargs)
            j = r.json()
            self._handle_scrape_error(j)
            self._num_found = j.get('total')
        return self._num_found

    def _handle_scrape_error(self, j):
        if 'error' in j:
            if all(s in j['error'].lower() for s in ['invalid', 'secret']):
                if not j['error'].endswith('.'):
                    j['error'] += '.'
                raise ValueError("{0} Try running 'ia configure' "
                                 "and retrying.".format(j['error']))
            raise ValueError(j.get('error'))

    def _get_item_from_search_result(self, search_result):
        return self.session.get_item(search_result['identifier'])

    def iter_as_results(self):
        return SearchIterator(self, self._make_results_generator())

    def iter_as_items(self):
        if six.PY2:
            _map = itertools.imap(self._get_item_from_search_result,
                                  self._make_results_generator())
        else:
            _map = map(self._get_item_from_search_result, self._make_results_generator())
        return SearchIterator(self, _map)

    def __len__(self):
        return self.num_found


class SearchIterator(object):
    """This class is an iterator wrapper for search results.

    It provides access to the underlying Search, and supports
    len() (since that is known initially)."""

    def __init__(self, search, iterator):
        self.search = search
        self.iterator = iterator

    def __len__(self):
        return self.search.num_found

    def __next__(self):
        return self.iterator.__next__()

    def next(self):
        return self.iterator.next()

    def __iter__(self):
        return self

    def __repr__(self):
        return '{0.__class__.__name__}({0.search!r}, {0.iterator!r})'.format(self)
