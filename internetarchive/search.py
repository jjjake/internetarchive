# -*- coding: utf-8 -*-
"""
internetarchive.search
~~~~~~~~~~~~~~~~~~~~~~

This module provides objects for interacting with the Archive.org
search engine.

:copyright: (c) 2015 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals

import itertools
from logging import getLogger

import six


log = getLogger(__name__)


class Search(object):
    """This class represents an archive.org item search. You can use
    this class to search for Archive.org items using the advanced search
    engine.

    Usage::

        >>> import internetarchive.search
        >>> search = internetarchive.search.Search('(uploader:jake@archive.org)')
        >>> for result in search:
        ...     print(result['identifier'])
    """

    def __init__(self, archive_session, query,
                 fields=None,
                 sorts=None,
                 params=None,
                 request_kwargs=None):
        params = params or {}

        self.session = archive_session
        self.query = query
        self.fields = fields or list()
        self.sorts = sorts or list()
        self.request_kwargs = request_kwargs or dict()
        self._num_found = None
        self.scrape_url = '{0}//archive.org/services/search/beta/scrape.php'.format(
            self.session.protocol)
        self.search_url = '{0}//archive.org/advancedsearch.php'.format(
            self.session.protocol)

        # Initialize params.
        default_params = dict(q=query)
        if 'page' not in params:
            default_params['size'] = 10000
        else:
            default_params['output'] = 'json'
        self.params = default_params.copy()
        self.params.update(params)

        # Set timeout.
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 12

        # Set retries.
        self.session._mount_http_adapter(max_retries=5)

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

        r = self.session.get(self.search_url,
                             params=self.params,
                             **self.request_kwargs)
        j = r.json()
        for item in j.get('response', {}).get('docs', []):
            yield item

    def _scrape(self):
        if self.fields:
            self.params['fields'] = ','.join(self.fields)
        if self.sorts:
            self.params['sorts'] = ','.join(self.sorts)
        remaining = True
        while remaining:
            r = self.session.get(self.scrape_url,
                                 params=self.params,
                                 **self.request_kwargs)
            j = r.json()
            if 'error' in j:
                raise ValueError(j.get('error'))

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
            p = dict(q=self.params['q'], rows=0, output='json')
            r = self.session.get(self.search_url, params=p, **self.request_kwargs)
            j = r.json()
            self._num_found = j.get('response', {}).get('numFound')
        return self._num_found

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
