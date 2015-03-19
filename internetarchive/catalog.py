try:
    import ujson as json
except ImportError:
    import json
import six
from six.moves.urllib.parse import parse_qsl

import requests.sessions

from . import session
from .utils import map2x


# Catalog class
# ________________________________________________________________________________________
class Catalog(object):
    """This class represents the Archive.org catalog. You can use this class to access
    tasks from the catalog::

        >>> import internetarchive
        >>> c = internetarchive.Catalog(identifier='jstor_ejc')
        >>> c.tasks[-1]
        CatalogTask(identifier=jstor_ejc, task_id=143919540, server=u'ia601503', command=u'archiv', submitter=u'jake@archive.org', row_type=-1)

    """

    ROW_TYPES = dict(
        green=0,
        blue=1,
        red=2,
        brown=9,
        purple=-1,
    )

    # init()
    # ____________________________________________________________________________________
    def __init__(self, identifier=None, task_ids=None, params=None, config=None,
                 verbose=None):
        """Get tasks from the Archive.org catalog. ``internetarchive`` must be configured
        with your logged-in-* cookies to use this function. If no arguments are provided,
        all queued tasks for the user will be returned.

        :type identifier: str
        :param identifier: (optional) The Archive.org identifier for which to retrieve
                           tasks for.

        :type task_ids: int or str
        :param task_ids: (optional) The task_ids to retrieve from the Archive.org catalog.

        :type params: dict
        :param params: (optional) The URL parameters to send with each request sent to the
                       Archive.org catalog API.

        :type config: dict
        :param secure: (optional) Configuration options for session.

        :type verbose: bool
        :param verbose: (optional) Set to ``True`` to retrieve verbose information for
                        each catalog task returned. Verbose is set to ``True`` by default.

        """
        task_ids = [] if not task_ids else task_ids
        params = {} if not params else params
        config = {} if not config else config
        verbose = '1' if verbose is None or verbose is True else '0'

        self.session = session.ArchiveSession(config)
        # Accessing the Archive.org catalog requires a users
        # logged-in-* cookies (i.e. you must be logged in).
        # Raise an exception if they are not set.
        if not self.session.cookies.get('logged-in-user'):
            raise NameError('logged-in-user cookie not set. Use `ia configure --cookies` '
                            'to add your logged-in-user cookie to your internetarchive '
                            'config file, or set the IA_LOGGED_IN_USER environment '
                            'variable.')
        elif not self.session.cookies.get('logged-in-sig'):
            raise NameError('logged-in-sig cookie not set. Use `ia configure --cookies` '
                            'to add your logged-in-sig cookie to your internetarchive '
                            'config file, or set the IA_LOGGED_IN_SIG environment '
                            'variable.')

        self.http_session = requests.sessions.Session()

        # Set cookies from config.
        self.http_session.cookies = self.session.cookies
        self.http_session.cookies['verbose'] = verbose

        # Params required to retrieve JSONP from the IA catalog.
        self.params = dict(
            json=2,
            output='json',
            callback='foo',
        )
        self.params.update(params)
        # Return user's current tasks as default.
        if not identifier and not task_ids and not params:
            self.params['justme'] = 1

        if task_ids:
            if not isinstance(task_ids, (set, list)):
                task_ids = [task_ids]
            task_ids = [str(t) for t in task_ids]
            self.params.update(dict(
                where='task_id in({tasks})'.format(tasks=','.join(task_ids)),
                history=99999999999999999999999,  # TODO: is there a better way?
            ))

        if identifier:
            self.url = 'http://archive.org/history/{id}'.format(id=identifier)
        elif task_ids:
            self.url = 'http://cat-tracey.archive.org/catalog.php'
        else:
            self.url = 'http://archive.org/catalog.php'

        # Get tasks.
        self.tasks = self._get_tasks()

        # Set row_type attrs.
        for key in self.ROW_TYPES:
            rows = [t for t in self.tasks if t.row_type == self.ROW_TYPES[key]]
            setattr(self, '{0}_rows'.format(key), rows)

    # _get_tasks()
    # ____________________________________________________________________________________
    def _get_tasks(self):
        r = self.http_session.get(self.url, params=self.params)
        content = r.content.decode('utf-8')
        # Convert JSONP to JSON (then parse the JSON).
        json_str = r.content[(content.index("(") + 1):content.rindex(")")]
        return [
            CatalogTask(t, http_session=self.http_session) for t in json.loads(json_str)
        ]


# CatalogTask class
# ________________________________________________________________________________________
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

    # init()
    # ____________________________________________________________________________________
    def __init__(self, columns, http_session=None):
        if not http_session:
            self._http_session = requests.sessions.Session()
        else:
            self._http_session = http_session

        for key, value in map2x(None, self.COLUMNS, columns):
            if key:
                setattr(self, key, value)
        # special handling for 'args' - parse it into a dict if it is a string
        if isinstance(self.args, six.string_types):
            self.args = dict(x for x in parse_qsl(self.args.encode('utf-8')))

    # __repr__()
    # ____________________________________________________________________________________
    def __repr__(self):
        return ('CatalogTask(identifier={identifier},'
                ' task_id={task_id!r}, server={server!r},'
                ' command={command!r},'
                ' submitter={submitter!r},'
                ' row_type={row_type})'.format(**self.__dict__))

    # __getitem__()
    # ____________________________________________________________________________________
    def __getitem__(self, key):
        """Dict-like access provided as backward compatibility."""
        if key in self.COLUMNS:
            return getattr(self, key, None)
        else:
            raise KeyError(key)

    # task_log()
    # ____________________________________________________________________________________
    def task_log(self):
        """Get task log.

        :rtype: str
        :returns: The task log as a string.

        """
        if self.task_id is None:
            raise ValueError('task_id is None')
        url = 'http://catalogd.archive.org/log/{0}'.format(self.task_id)
        p = dict(full=1)
        r = self._http_session.get(url, params=p)
        r.raise_for_status()
        return r.content.decode('utf-8')
