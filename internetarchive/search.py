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

import six


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
                 params=None,
                 config=None,
                 request_kwargs=None):
        fields = [] if not fields else fields
        # Support str or list values for fields param.
        fields = [fields] if not isinstance(
            fields, (list, set, tuple)) else fields

        params = {} if not params else params
        config = {} if not config else config
        request_kwargs = {} if not request_kwargs else request_kwargs

        self.session = archive_session
        self.request_kwargs = request_kwargs
        self.url = '{0}//archive.org/advancedsearch.php'.format(self.session.protocol)
        default_params = dict(
            q=query,
            rows=250,
        )

        # Set timeout.
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 12

        # Set retries.
        self.session._mount_http_adapter(max_retries=5)

        # Sort by score if no other sort is provided -- if page parameter is
        # not provided.
        has_page_param = 'page' in params
        has_sort_param = any(k.startswith('sort') for k, v in params.items())
        if not (has_page_param or has_sort_param):
            default_params['sort[0]'] = 'identifier asc'

        self.params = default_params.copy()
        self.params.update(params)
        if not self.params.get('output'):
            self.params['output'] = 'json'

        for k, v in enumerate(fields):
            key = 'fl[{0}]'.format(k)
            self.params[key] = v
        self._search_info = self._get_search_info()
        self.num_found = self._search_info['response']['numFound']
        self.query = self._search_info['responseHeader']['params']['q']

    def __repr__(self):
        return ('Search(query={query!r}, '
                'num_found={num_found!r})'.format(**self.__dict__))

    def _get_search_info(self):
        info_params = self.params.copy()
        info_params['rows'] = 0
        r = self.session.get(self.url, params=info_params, **self.request_kwargs)
        results = r.json()
        del results['response']['docs']
        return results

    def _get_item_from_search_result(self, search_result):
        return self.session.get_item(search_result['identifier'])

    def __iter__(self):
        return self.iter_as_results()

    def __len__(self):
        return self.num_found

    def make_results_generator(self):
        """Generator for iterating over search results"""
        start_page = 1
        end_page = int((self.num_found / int(self.params['rows'])) + 2)
        if 'page' in self.params:
            start_page = int(self.params['page'])
            end_page = start_page + 1

        for page in range(start_page, end_page):
            self.params['page'] = page
            r = self.session.get(self.url, params=self.params, **self.request_kwargs)
            results = r.json()
            for doc in results['response']['docs']:
                yield doc

    def iter_as_results(self):
        return SearchIterator(self, self.make_results_generator())

    def iter_as_items(self):
        """Returns iterator of search results as full Items"""
        fields = [v for (k, v) in self.params.items() if k.startswith('fl[')]
        if fields and not any(f == 'identifier' for f in fields):
            raise KeyError('This search did not include item identifiers!')
        if six.PY2:
            _map = itertools.imap(self._get_item_from_search_result,
                                  self.make_results_generator())
        else:
            _map = map(self._get_item_from_search_result, self.make_results_generator())
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
