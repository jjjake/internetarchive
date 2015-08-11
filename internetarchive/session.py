from __future__ import absolute_import
import os
import logging

import requests.sessions
import requests.cookies
from requests.exceptions import HTTPError
import requests.adapters

from . import config as config_module
from . import item, search, catalog


class ArchiveSession(requests.sessions.Session):

    log_level = {
        'CRITICAL': 50,
        'ERROR':    40,
        'WARNING':  30,
        'INFO':     20,
        'DEBUG':    10,
        'NOTSET':   0,
    }

    FmtString = u'%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    def __init__(self, config=None, config_file=None, http_adapter_kwargs=None):
        super(ArchiveSession, self).__init__()
        http_adapter_kwargs = {} if not http_adapter_kwargs else http_adapter_kwargs

        self.config = config_module.get_config(config, config_file)
        s3_config = self.config.get('s3', {})
        max_retries = http_adapter_kwargs.get('max_retries', 10)

        self.cookies.update(self.config.get('cookies', {}))
        self.secure = self.config.get('secure', False)
        self.protocol = 'https:' if self.secure else 'http:'
        self.access_key = self.config.get('s3', {}).get('access')
        self.secret_key = self.config.get('s3', {}).get('secret')
        self.log = logging.getLogger(__name__)

        max_retries_adapter = requests.adapters.HTTPAdapter(**http_adapter_kwargs)
        self.mount('{0}//'.format(self.protocol), max_retries_adapter)

        logging_config = self.config.get('logging', {})
        if logging_config:    
            self.set_file_logger(
                self.log_level[logging_config.get('level', 'NOTSET')],
                logging_config.get('file', 'internetarchive.log'))

    def set_file_logger(self, log_level, path, logger_name='internetarchive'):
        """Convenience function to quickly configure any level of
        logging to a file.

        :type log_level: int
        :param log_level: A log level as specified in the `logging` module

        :type path: string
        :param path: Path to the log file. The file will be created
        if it doesn't already exist.

        """
        self.log = logging.getLogger(logger_name)
        self.log.setLevel(logging.DEBUG)
        fh = logging.FileHandler(path)
        fh.setLevel(log_level)
        formatter = logging.Formatter(self.FmtString)
        fh.setFormatter(formatter)
        self.log.addHandler(fh)

    _ITEM_MEDIATYPE_TABLE={'collection':item.Collection}
    # get_item()
    # ____________________________________________________________________________________
    def get_item(self, identifier, item_metadata=None, request_kwargs=None):
        request_kwargs = {} if not request_kwargs else request_kwargs
        if not item_metadata:
            item_metadata = self.get_metadata(identifier, request_kwargs)
        return self._ITEM_MEDIATYPE_TABLE.get(item_metadata.get('metadata',{}).get('mediatype',''), item.Item)(self, identifier, item_metadata)

    # get_metadata()
    # ____________________________________________________________________________________
    def get_metadata(self, identifier, request_kwargs=None):
        """Get an item's metadata from the `Metadata API
        <http://blog.archive.org/2013/07/04/metadata-api/>`__

        :type identifier: str
        :param identifier: Globally unique Archive.org identifier.

        :rtype: dict
        :returns: Metadat API response.

        """
        request_kwargs = {} if not request_kwargs else request_kwargs
        url = '{protocol}//archive.org/metadata/{identifier}'.format(
                protocol=self.protocol, identifier=identifier)
        try:
            resp = self.get(url, **request_kwargs)
            resp.raise_for_status()
        except HTTPError as exc:
            error_msg = 'Error retrieving metadata from {0}, {1}'.format(resp.url, exc)
            self.log.error(error_msg)
            raise HTTPError(error_msg)
        return resp.json()

    # s3_is_overloaded()
    # ____________________________________________________________________________________
    def search_items(self, query,
                     fields=None,
                     params=None,
                     config=None,
                     v2=None,
                     request_kwargs=None):
        """Search for items on Archive.org.

        :type query: str
        :param query: The Archive.org search query to yield results for. Refer to
                      https://archive.org/advancedsearch.php#raw for help formatting your
                      query.

        :type fields: bool
        :param fields: (optional) The metadata fields to return in the search results.

        :type params: dict
        :param params: (optional) The URL parameters to send with each request sent to the
                       Archive.org Advancedsearch Api.

        :type config: dict
        :param secure: (optional) Configuration options for session.

        :type v2: bool
        :param v2: To use the archive.org/v2 Advancedsearch API, set v2 to ``True``.

        :returns: A :class:`Search` object, yielding search results.
        """
        request_kwargs = {} if not request_kwargs else request_kwargs
        return search.Search(self, query,
                      fields=fields,
                      params=params,
                      config=config,
                      v2=v2,
                      request_kwargs=request_kwargs)

    # get_tasks()
    # ________________________________________________________________________________________
    def get_tasks(self,
                  identifier=None,
                  task_ids=None,
                  task_type=None,
                  params=None,
                  config=None,
                  verbose=None,
                  request_kwargs=None):
        """Get tasks from the Archive.org catalog. ``internetarchive`` must be configured
        with your logged-in-* cookies to use this function. If no arguments are provided,
        all queued tasks for the user will be returned.

        :type identifier: str
        :param identifier: (optional) The Archive.org identifier for which to retrieve tasks
                           for.

        :type task_ids: int or str
        :param task_ids: (optional) The task_ids to retrieve from the Archive.org catalog.

        :type task_type: str
        :param task_type: (optional) The type of tasks to retrieve from the Archive.org
                          catalog. The types can be either "red" for failed tasks, "blue" for
                          running tasks, "green" for pending tasks, "brown" for paused tasks,
                          or "purple" for completed tasks.

        :type params: dict
        :param params: (optional) The URL parameters to send with each request sent to the
                       Archive.org catalog API.

        :type config: dict
        :param secure: (optional) Configuration options for session.

        :type verbose: bool
        :param verbose: (optional) Set to ``True`` to retrieve verbose information for each
                        catalog task returned. verbose is set to ``True`` by default.

        :returns: A set of :class:`CatalogTask` objects.
        """
        request_kwargs = {} if not request_kwargs else request_kwargs
        _catalog = catalog.Catalog(self,
                           identifier=identifier,
                           task_ids=task_ids,
                           params=params,
                           config=config,
                           verbose=verbose,
                           request_kwargs=request_kwargs)
        if task_type:
            return eval('_catalog.{0}_rows'.format(task_type.lower()))
        else:
            return _catalog.tasks

    # s3_is_overloaded()
    # ____________________________________________________________________________________
    def s3_is_overloaded(self, identifier=None, access_key=None):
        u = '{protocol}//s3.us.archive.org'.format(protocol=self.protocol)
        p = dict(
            check_limit=1,
            accesskey=access_key,
            bucket=identifier,
        )
        r = self.get(u, params=p)
        j = r.json()
        if j.get('over_limit') == 0:
            return False
        else:
            return True
