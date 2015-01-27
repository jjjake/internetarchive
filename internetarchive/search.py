import requests.sessions

from . import session


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
    # init()
    # ____________________________________________________________________________________
    def __init__(self, query, fields=['identifier'], params={}, config=None, v2=False):
        self.session = session.ArchiveSession(config)
        self.http_session = requests.sessions.Session()
        self.url = 'http://archive.org/advancedsearch.php'
        default_params = dict(
            q=query,
            rows=100,
        )

        if v2:
            # Use "1" as value to not confuse IA analytics.
            self.session.cookies['ui3'] = '1'
            self.http_session.cookies = self.session.cookies

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

    # __repr__()
    # ____________________________________________________________________________________
    def __repr__(self):
        return ('Search(query={query!r}, '
                'num_found={num_found!r})'.format(**self.__dict__))

    # _get_search_info()
    # ____________________________________________________________________________________
    def _get_search_info(self):
        info_params = self.params.copy()
        info_params['rows'] = 0
        r = self.http_session.get(self.url, params=self.params)
        results = r.json()
        del results['response']['docs']
        return results

    # __iter__()
    # ____________________________________________________________________________________
    def __iter__(self):
        """Generator for iterating over search results"""
        total_pages = ((self.num_found // self.params['rows']) + 2)
        for page in range(1, total_pages):
            self.params['page'] = page
            r = self.http_session.get(self.url, params=self.params)
            results = r.json()
            for doc in results['response']['docs']:
                yield doc
