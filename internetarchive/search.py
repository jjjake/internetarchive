from __future__ import absolute_import, unicode_literals, print_function

import itertools

# Search class
# ________________________________________________________________________________________
class Search(object):
    """This class represents an archive.org item search. You can use
    this class to search for archive.org items using the advanced
    search engine.

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
                 v2=None,
                 request_kwargs=None):
        fields = [] if not fields else fields
        # Support str or list values for fields param.
        fields = [fields] if not isinstance(fields, (list, set, tuple)) else fields

        params = {} if not params else params
        config = {} if not config else config
        v2 = False if not v2 else True
        request_kwargs = {} if not request_kwargs else request_kwargs

        self.session = archive_session
        self.request_kwargs = request_kwargs
        self.url = '{0}//archive.org/advancedsearch.php'.format(self.session.protocol)
        default_params = dict(
            q=query,
            rows=100,
        )

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
        return self.session.get_item(search_result[u'identifier'])

    def __iter__(self):
        return SearchIterator(self, self.iter_as_results())

    def __len__(self):
        return self.num_found

    def iter_as_results(self):
        """Generator for iterating over search results"""
        total_pages = ((self.num_found / int(self.params['rows'])) + 2)
        for page in range(1, total_pages):
            self.params['page'] = page
            r = self.session.get(self.url, params=self.params, **self.request_kwargs)
            results = r.json()
            for doc in results['response']['docs']:
                yield doc

    def iter_as_items(self):
        fields = [v for (k,v) in self.params.iteritems() if k.startswith('fl[')]
        if fields and not any(f=='identifier' for f in fields):
            raise KeyError('This search did not include item identifiers!')
        item_iterator = itertools.imap(self._get_item_from_search_result,
                                       self.iter_as_results())
        return SearchIterator(self, item_iterator)

class SearchIterator(object):

    def __init__(self, search, iterator):
        self.search = search
        self.iterator = iterator

    def __len__(self):
        return self.search.num_found

    def next(self):
        return self.iterator.next()

    def __iter__(self):
        return self

    def __repr__(self):
        return '{0.__class__.__name__}({0.search!r}, {0.iterator!r})'.format(self)
