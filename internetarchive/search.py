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
import itertools
from logging import getLogger

from requests.exceptions import ReadTimeout

from internetarchive.auth import S3Auth

log = getLogger(__name__)


class Search:
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
                 full_text_search=None,
                 dsl_fts=None,
                 request_kwargs=None,
                 max_retries=None):
        params = params or {}

        self.session = archive_session
        self.dsl_fts = False if not dsl_fts else True
        if self.dsl_fts or full_text_search:
            self.fts = True
        else:
            self.fts = False
        self.query = query
        if self.fts and not self.dsl_fts:
            self.query = f'!L {self.query}'
        self.fields = fields or []
        self.sorts = sorts or []
        self.request_kwargs = request_kwargs or {}
        self._num_found = None
        self.fts_url = f'{self.session.protocol}//be-api.us.archive.org/ia-pub-fts-api'
        self.scrape_url = f'{self.session.protocol}//{self.session.host}/services/search/v1/scrape'
        self.search_url = f'{self.session.protocol}//{self.session.host}/advancedsearch.php'
        if self.session.access_key and self.session.secret_key:
            self.auth = S3Auth(self.session.access_key, self.session.secret_key)
        else:
            self.auth = None
        self.max_retries = max_retries if max_retries is not None else 5

        # Initialize params.
        default_params = {'q': self.query}
        if 'page' not in params:
            if 'rows' in params:
                params['page'] = 1
            else:
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
        return f'Search(query={self.query!r})'

    def __iter__(self):
        return self.iter_as_results()

    def _advanced_search(self):
        # Always return identifier.
        if 'identifier' not in self.fields:
            self.fields.append('identifier')
        for k, v in enumerate(self.fields):
            self.params[f'fl[{k}]'] = v

        for i, field in enumerate(self.sorts):
            self.params[f'sort[{i}]'] = field

        self.params['output'] = 'json'

        r = self.session.get(self.search_url,
                             params=self.params,
                             auth=self.auth,
                             **self.request_kwargs)
        j = r.json()
        num_found = int(j.get('response', {}).get('numFound', 0))
        if not self._num_found:
            self._num_found = num_found
        if j.get('error'):
            yield j
        yield from j.get('response', {}).get('docs', [])

    def _scrape(self):
        if self.fields:
            self.params['fields'] = ','.join(self.fields)
        if self.sorts:
            self.params['sorts'] = ','.join(self.sorts)
        i = 0
        num_found = None
        while True:
            r = self.session.post(self.scrape_url,
                                  params=self.params,
                                  auth=self.auth,
                                  **self.request_kwargs)
            j = r.json()
            if j.get('error'):
                yield j
            if not num_found:
                num_found = int(j.get('total') or '0')
            if not self._num_found:
                self._num_found = num_found
            self._handle_scrape_error(j)

            self.params['cursor'] = j.get('cursor')
            for item in j['items']:
                i += 1
                yield item
            if 'cursor' not in j:
                if i != num_found:
                    raise ReadTimeout('The server failed to return results in the'
                                      f' allotted amount of time for {r.request.url}')
                break

    def _full_text_search(self):
        d = {
            'q': self.query,
            'size': '10000',
            'from': '0',
            'scroll': 'true',
        }

        if 'scope' in self.params:
            d['scope'] = self.params['scope']

        if 'size' in self.params:
            d['scroll'] = False
            d['size'] = self.params['size']

        while True:
            r = self.session.post(self.fts_url,
                                  json=d,
                                  auth=self.auth,
                                  **self.request_kwargs)
            j = r.json()
            scroll_id = j.get('_scroll_id')
            hits = j.get('hits', {}).get('hits')
            if not hits:
                return
            yield from hits
            if not hits or d['scroll'] is False:
                break
            d['scroll_id'] = scroll_id

    def _make_results_generator(self):
        if self.fts:
            return self._full_text_search()
        if 'user_aggs' in self.params:
            return self._user_aggs()
        elif 'page' in self.params:
            return self._advanced_search()
        else:
            return self._scrape()

    def _user_aggs(self):
        """Experimental support for user aggregations.
        """
        self.params['page'] = '1'
        self.params['rows'] = '1'
        self.params['output'] = 'json'
        r = self.session.get(self.search_url,
                             params=self.params,
                             auth=self.auth,
                             **self.request_kwargs)
        j = r.json()
        if j.get('error'):
            yield j
        for agg in j.get('response', {}).get('aggregations', {}).items():
            yield {agg[0]: agg[1]}

    @property
    def num_found(self):
        if not self._num_found:
            if not self.fts:
                p = self.params.copy()
                p['total_only'] = 'true'
                r = self.session.post(self.scrape_url,
                                      params=p,
                                      auth=self.auth,
                                      **self.request_kwargs)
                j = r.json()
                self._handle_scrape_error(j)
                self._num_found = j.get('total')
            else:
                self.params['q'] = self.query
                r = self.session.get(self.fts_url,
                                     params=self.params,
                                     auth=self.auth,
                                     **self.request_kwargs)
                j = r.json()
                self._num_found = j.get('hits', {}).get('total')
        return self._num_found

    def _handle_scrape_error(self, j):
        if 'error' in j:
            if all(s in j['error'].lower() for s in ['invalid', 'secret']):
                if not j['error'].endswith('.'):
                    j['error'] += '.'
                raise ValueError(f"{j['error']} Try running 'ia configure' and retrying.")
            raise ValueError(j.get('error'))

    def _get_item_from_search_result(self, search_result):
        return self.session.get_item(search_result['identifier'])

    def iter_as_results(self):
        return SearchIterator(self, self._make_results_generator())

    def iter_as_items(self):
        _map = map(self._get_item_from_search_result, self._make_results_generator())
        return SearchIterator(self, _map)

    def __len__(self):
        return self.num_found


class SearchIterator:
    """This class is an iterator wrapper for search results.

    It provides access to the underlying Search, and supports
    len() (since that is known initially)."""

    def __init__(self, search, iterator):
        self.search = search
        self.iterator = iterator

    def __len__(self):
        return self.search.num_found

    def __next__(self):
        return next(self.iterator)

    def __iter__(self):
        return self

    def __repr__(self):
        return f'{self.__class__.__name__}({self.search!r}, {self.iterator!r})'
