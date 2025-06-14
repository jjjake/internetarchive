#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
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

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

from logging import getLogger
from typing import Generator, Iterable

from requests.exceptions import ReadTimeout
from urllib3 import Retry

from internetarchive.auth import S3Auth
from internetarchive.item import Item
from internetarchive.session import ArchiveSession

log = getLogger(__name__)

class SearchIterator(list):
    """This class is an iterator wrapper for search results.

    It provides access to the underlying Search, and supports
    len() (since that is known initially)."""

    def __init__(self, search: Search, iterator: Iterable[dict | Item]):
        self.search = search
        self.iterator = iterator

    def __len__(self) -> int:
        return int(self.search.num_found) # type: ignore

    def __next__(self) -> dict | Item:
        return next(self.iterator) # type: ignore

    def __iter__(self) -> SearchIterator:
        return self

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.search!r}, {self.iterator!r})'


class Search:
    """This class represents an archive.org item search. You can use
    this class to search for Archive.org items using the advanced search
    engine. By default it uses the scaping API, see for
    `documentation <https://archive.org/help/aboutsearch.htm>`__,
    which uses the same query Lucene-like queries supported by
    Internet Archive Advanced Search. See the advance search page for
    `documentation <https://archive.org/advancedsearch.php>`__,
    when using `pages`.

    :param archive_session: A session
    :type archive_session: ArchiveSession
    :param query: Lucene-like query string
    :type query: str
    :param fields: Fields to return. This always includes `identifier`.
    :type fields: list[str] or None
    :param sorts: Sort by field (value: 'desc' or 'asc')
    :type sorts: dict or None
    :param params: ?
    :type params: dict or None
    :param full_text_search: Use the undocumented full text search API
    :type full_text_search: bool or None
    :param dsl_fts: ?
    :type dsl_fts: dict or None
    :param request_kwargs: kwargs passed to request
    :type request_kwargs: dict or None
    :param max_retries: Max retries tried by request
    :type max_retries: int or Retry

    Usage::

        >>> from internetarchive.session import ArchiveSession
        >>> from internetarchive.search import Search
        >>> s = ArchiveSession()
        >>> search = Search(s, '(uploader:jake@archive.org)')
        >>> for result in search:
        ...     print(result['identifier'])
    """

    def __init__(self,
                 archive_session: ArchiveSession,
                 query: str,
                 fields: list[str] | None = None, # UP007
                 sorts: dict | None = None,
                 params: dict | None = None,
                 full_text_search: bool | None = None,
                 dsl_fts: bool | None = None,
                 request_kwargs: dict | None = None,
                 max_retries: int | Retry | None = None):

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
        self.sorts = sorts or {}
        self.request_kwargs = request_kwargs or {}
        self._num_found: int | None = None
        self.fts_url = f'{self.session.protocol}//be-api.us.archive.org/ia-pub-fts-api'
        self.scrape_url = f'{self.session.protocol}//{self.session.host}/services/search/v1/scrape'
        self.search_url = f'{self.session.protocol}//{self.session.host}/advancedsearch.php'
        if self.session.access_key and self.session.secret_key:
            self.auth: S3Auth | None = S3Auth(self.session.access_key, self.session.secret_key)
        else:
            self.auth = None
        self.max_retries = max_retries if max_retries is not None else 5

        # Initialize params.
        default_params = {'q': self.query}
        if 'page' not in params:
            if 'rows' in params:
                params['page'] = 1
            else:
                default_params["count"] = "10000"
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
        self.session.mount_http_adapter(max_retries=self.max_retries) # type: ignore

    def __repr__(self):
        return f'Search(query={self.query!r})'

    def __iter__(self) -> SearchIterator:
        return self.iter_as_results()

    def _get_item_from_search_result(
                                     self,
                                     search_result: SearchIterator
                                    ) -> Item:
        return self.session.get_item(search_result['identifier']) # type: ignore

    def iter_as_results(self) -> SearchIterator:
        return SearchIterator(self, self._make_results_generator()) # type: ignore

    def iter_as_items(self) -> SearchIterator:
        """Returns an iterator over the fetched :class:`internetarchive.item.Item`s.

        This fetches an :class:`internetarchive.item.Item` from IA.
        """
        _map = map(self._get_item_from_search_result, self._make_results_generator()) # type: ignore
        return SearchIterator(self, _map)

    def _make_results_generator(self) -> Generator[dict, None, None]:
        if self.fts:
            return self._full_text_search()
        if 'user_aggs' in self.params:
            return self._user_aggs()
        elif 'page' in self.params:
            return self._advanced_search()
        else:
            return self._scrape()

    def _advanced_search(self) -> Generator[dict, None, None]:
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

    def _scrape(self) -> Generator[dict, None, None]:
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

    def _full_text_search(self) -> Generator[dict, None, None]:
        d = {
            'q': self.query,
            'size': '10000',
            'from': '0',
            'scroll': 'true',
        }

        if 'scope' in self.params:
            d['scope'] = self.params['scope']

        if 'size' in self.params:
            d['scroll'] = str(False)
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

    def _user_aggs(self) -> Generator[dict, None, None]:
        """Experimental support for user aggregations.
        """
        del self.params['count']  # advanced search will error if this param is present!
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
    def num_found(self) -> int | None:
        if not self._num_found:
            if not self.fts and 'page' in self.params:
                p = self.params.copy()
                p['output'] = 'json'
                r = self.session.get(self.search_url,
                                     params=p,
                                     auth=self.auth,
                                     **self.request_kwargs)
                j = r.json()
                num_found = int(j.get('response', {}).get('numFound', 0))
                if not self._num_found:
                    self._num_found = num_found
            elif not self.fts:
                p = self.params.copy()
                p['total_only'] = 'true'
                r = self.session.post(self.scrape_url,
                                      params=p,
                                      auth=self.auth,
                                      **self.request_kwargs)
                j = r.json()
                log.info(r.url)
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

    def _handle_scrape_error(self, j: dict) -> None:
        if 'error' in j:
            if all(s in j['error'].lower() for s in ['invalid', 'secret']):
                if not j['error'].endswith('.'):
                    j['error'] += '.'
                raise ValueError(f"{j['error']} Try running 'ia configure' and retrying.")
            raise ValueError(j.get('error'))

    def __len__(self) -> int | None:
        return self.num_found
