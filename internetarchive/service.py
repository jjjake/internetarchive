try:
    import ujson as json
except ImportError:
    import json
import urllib
import urllib2

from . import config



# Search class
#_________________________________________________________________________________________
class Search(object):
    """This class represents an archive.org item search. You can use 
    this class to search for archive.org items using the advanced 
    search engine.

    Usage::

        >>> import internetarchive
        >>> search = internetarchive.Search('(uploader:jake@archive.org)')
        >>> for result in search.results:
        ...     print result['identifier']

    """

    # init()
    #_____________________________________________________________________________________
    def __init__(self, query, fields=['identifier'], params={}):
        self._base_url = 'http://archive.org/advancedsearch.php'
        self.query = query
        self.params = dict(dict(
                q = self.query,
                output = params.get('output', 'json'),
                rows = 100,
        ).items() + params.items())
        # Updata params dict with fields.
        for k, v in enumerate(fields):
            key = 'fl[{0}]'.format(k)
            self.params[key] = v
        self.encoded_params = urllib.urlencode(self.params)
        self.search_info = self._get_search_info()
        self.num_found = self.search_info['response']['numFound']


    # __repr__()
    #_____________________________________________________________________________________
    def __repr__(self):
        return ('Search(query={query!r}, '
                'num_found={num_found!r})'.format(**self.__dict__))


    # _get_search_info()
    #_____________________________________________________________________________________
    def _get_search_info(self):
        info_params = self.params.copy()
        info_params['rows'] = 0
        encoded_info_params = urllib.urlencode(info_params)
        f = urllib.urlopen(self._base_url, encoded_info_params)
        results = json.loads(f.read())
        del results['response']['docs']
        return results


    # _iter_results()
    #_____________________________________________________________________________________
    def results(self):
        """Generator for iterating over search results"""
        total_pages = ((self.num_found / self.params['rows']) + 2)
        for page in range(1, total_pages):
            self.params['page'] = page
            encoded_params = urllib.urlencode(self.params)
            f = urllib.urlopen(self._base_url, encoded_params)
            results = json.loads(f.read())
            for doc in results['response']['docs']:
                yield doc


#_________________________________________________________________________________________
class Catalog(object):
    """:todo: Document Catalog Class."""
    GREEN = 0
    BLUE = 1
    RED = 2
    BROWN = 9

    # init()
    #_____________________________________________________________________________________
    def __init__(self, params=None):
        url = 'http://archive.org/catalog.php'
        if params is None:
            params = dict(justme = 1)

        # Add params required to retrieve JSONP from the IA catalog.
        params['json'] = 2
        params['output'] = 'json'
        params['callback'] = 'foo'
        params = urllib.urlencode(params)

        logged_in_user, logged_in_sig = config.get_cookies()
        cookies = ('logged-in-user={0}; '
                   'logged-in-sig={1}; '
                   'verbose=1'.format(logged_in_user, logged_in_sig))

        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie', cookies))
        f = opener.open(url, params)

        # Convert JSONP to JSON (then parse the JSON).
        jsonp_str = f.read()
        json_str = jsonp_str[(jsonp_str.index("(") + 1):jsonp_str.rindex(")")]

        tasks_json = json.loads(json_str)
        self.tasks = [CatalogTask(t) for t in tasks_json]
        

    # filter_tasks()
    #_____________________________________________________________________________________
    def filter_tasks(self, pred):
        return [t for t in self.tasks if pred(t)]


    # tasks_by_type()
    #_____________________________________________________________________________________
    def tasks_by_type(self, row_type):
        return self.filter_tasks(lambda t: t.row_type == row_type)

    # green_rows()
    #_____________________________________________________________________________________
    @property
    def green_rows(self):
        return self.tasks_by_type(self.GREEN)


    # blue_rows()
    #_____________________________________________________________________________________
    @property
    def blue_rows(self):
        return self.tasks_by_type(self.BLUE)


    # red_rows()
    #_____________________________________________________________________________________
    @property
    def red_rows(self):
        return self.tasks_by_type(self.RED)


    # brown_rows()
    #_____________________________________________________________________________________
    @property
    def brown_rows(self):
        return self.tasks_by_type(self.BROWN)


# CatalogTask class
#_________________________________________________________________________________________
class CatalogTask(object):
    """represents catalog task.
    """
    COLUMNS = ('identifier', 'server', 'command', 'time', 'submitter',
               'args', 'task_id', 'row_type')

    def __init__(self, columns):
        """:param columns: array of values, typically returned by catalog
        web service. see COLUMNS for the column name.
        """
        for a, v in map(None, self.COLUMNS, columns):
            if a: setattr(self, a, v)
        # special handling for 'args' - parse it into a dict if it is a string
        if isinstance(self.args, basestring):
            self.args = dict(x for x in urllib2.urlparse.parse_qsl(self.args))

    def __repr__(self):
        return ('CatalogTask(identifier={identifier},'
                ' task_id={task_id!r}, server={server!r},'
                ' command={command!r},'
                ' submitter={submitter!r},'
                ' row_type={row_type})'.format(**self.__dict__))

    def __getitem__(self, k):
        """dict-like access privided as backward compatibility."""
        if k in self.COLUMNS:
            return getattr(self, k, None)
        else:
            raise KeyError(k)

    def open_task_log(self):
        """return file-like reading task log."""
        if self.task_id is None:
            raise ValueError('task_id is None')
        url = 'http://catalogd.archive.org/log/{0}'.format(self.task_id)
        return urllib2.urlopen(url)
