# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2017 Internet Archive
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
internetarchive.api
~~~~~~~~~~~~~~~~~~~

This module implements the Internetarchive API.

:copyright: (C) 2012-2017 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

from six.moves import input
from getpass import getpass
import requests

from internetarchive import session
from internetarchive import config as config_module
from internetarchive import auth
from internetarchive.exceptions import AuthenticationError


def get_session(config=None, config_file=None, debug=None, http_adapter_kwargs=None):
    """Return a new :class:`ArchiveSession` object. The :class:`ArchiveSession`
    object is the main interface to the ``internetarchive`` lib. It allows you to
    persist certain parameters across tasks.

    :type config: dict
    :param config: (optional) A dictionary used to configure your session.

    :type config_file: str
    :param config_file: (optional) A path to a config file used to configure your session.

    :type http_adapter_kwargs: dict
    :param http_adapter_kwargs: (optional) Keyword arguments that
                                :py:class:`requests.adapters.HTTPAdapter` takes.

    :returns: :class:`ArchiveSession` object.

    Usage:

        >>> from internetarchive import get_session
        >>> config = dict(s3=dict(access='foo', secret='bar'))
        >>> s = get_session(config)
        >>> s.access_key
        'foo'

    From the session object, you can access all of the functionality of the
    ``internetarchive`` lib:

        >>> item = s.get_item('nasa')
        >>> item.download()
        nasa: ddddddd - success
        >>> s.get_tasks(task_ids=31643513)[0].server
        'ia311234'
    """
    return session.ArchiveSession(config, config_file, debug, http_adapter_kwargs)


def get_item(identifier,
             config=None,
             config_file=None,
             archive_session=None,
             debug=None,
             http_adapter_kwargs=None,
             request_kwargs=None):
    """Get an :class:`Item` object.

    :type identifier: str
    :param identifier: The globally unique Archive.org item identifier.

    :type config: dict
    :param config: (optional) A dictionary used to configure your session.

    :type config_file: str
    :param config_file: (optional) A path to a config file used to configure your session.

    :type archive_session: :class:`ArchiveSession`
    :param archive_session: (optional) An :class:`ArchiveSession` object can be provided
                            via the ``archive_session`` parameter.

    :type http_adapter_kwargs: dict
    :param http_adapter_kwargs: (optional) Keyword arguments that
                                :py:class:`requests.adapters.HTTPAdapter` takes.

    :type request_kwargs: dict
    :param request_kwargs: (optional) Keyword arguments that
                           :py:class:`requests.Request` takes.

    Usage:
        >>> from internetarchive import get_item
        >>> item = get_item('nasa')
        >>> item.item_size
        121084
    """
    if not archive_session:
        archive_session = get_session(config, config_file, debug, http_adapter_kwargs)
    return archive_session.get_item(identifier, request_kwargs=request_kwargs)


def get_files(identifier,
              files=None,
              formats=None,
              glob_pattern=None,
              on_the_fly=None,
              **get_item_kwargs):
    """Get :class:`File` objects from an item.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: iterable
    :param files: (optional) Only return files matching the given filenames.

    :param formats: iterable
    :param formats: (optional) Only return files matching the given formats.

    :type glob_pattern: str
    :param glob_pattern: (optional) Only return files matching the given glob pattern.

    :type on_the_fly: bool
    :param on_the_fly: (optional) Include on-the-fly files (i.e. derivative EPUB,
                       MOBI, DAISY files).

    :param \*\*get_item_kwargs: (optional) Arguments that ``get_item()`` takes.

    Usage:
        >>> from internetarchive import get_files
        >>> fnames = [f.name for f in get_files('nasa', glob_pattern='*xml')]
        >>> print(fnames)
        ['nasa_reviews.xml', 'nasa_meta.xml', 'nasa_files.xml']
    """
    item = get_item(identifier, **get_item_kwargs)
    return item.get_files(files, formats, glob_pattern, on_the_fly)


def modify_metadata(identifier, metadata,
                    target=None,
                    append=None,
                    priority=None,
                    access_key=None,
                    secret_key=None,
                    debug=None,
                    request_kwargs=None,
                    **get_item_kwargs):
    """Modify the metadata of an existing item on Archive.org.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :type metadata: dict
    :param metadata: Metadata used to update the item.

    :type target: str
    :param target: (optional) The metadata target to update. Defaults to `metadata`.

    :type append: bool
    :param append: (optional) set to True to append metadata values to current values
                   rather than replacing. Defaults to ``False``.

    :type priority: int
    :param priority: (optional) Set task priority.

    :type access_key: str
    :param access_key: (optional) IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: (optional) IA-S3 secret_key to use when making the given request.

    :type debug: bool
    :param debug: (optional) set to True to return a :class:`requests.Request <Request>`
                  object instead of sending request. Defaults to ``False``.

    :param \*\*get_item_kwargs: (optional) Arguments that ``get_item`` takes.

    :returns: :class:`requests.Response` object or :class:`requests.Request` object if
              debug is ``True``.
    """
    item = get_item(identifier, **get_item_kwargs)
    return item.modify_metadata(metadata, target, append, priority, access_key,
                                secret_key, debug, request_kwargs)


def upload(identifier, files,
           metadata=None,
           headers=None,
           access_key=None,
           secret_key=None,
           queue_derive=None,
           verbose=None,
           verify=None,
           checksum=None,
           delete=None,
           retries=None,
           retries_sleep=None,
           debug=None,
           request_kwargs=None,
           **get_item_kwargs):
    """Upload files to an item. The item will be created if it does not exist.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: The filepaths or file-like objects to upload. This value can be an
                  iterable or a single file-like object or string.

    :type metadata: dict
    :param metadata: (optional) Metadata used to create a new item. If the item already
                     exists, the metadata will not be updated -- use ``modify_metadata``.

    :type headers: dict
    :param headers: (optional) Add additional HTTP headers to the request.

    :type access_key: str
    :param access_key: (optional) IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: (optional) IA-S3 secret_key to use when making the given request.

    :type queue_derive: bool
    :param queue_derive: (optional) Set to False to prevent an item from being derived
                         after upload.

    :type verbose: bool
    :param verbose: (optional) Display upload progress.

    :type verify: bool
    :param verify: (optional) Verify local MD5 checksum matches the MD5 checksum of the
                   file received by IAS3.

    :type checksum: bool
    :param checksum: (optional) Skip uploading files based on checksum.

    :type delete: bool
    :param delete: (optional) Delete local file after the upload has been successfully
                   verified.

    :type retries: int
    :param retries: (optional) Number of times to retry the given request if S3 returns a
                    503 SlowDown error.

    :type retries_sleep: int
    :param retries_sleep: (optional) Amount of time to sleep between ``retries``.

    :type debug: bool
    :param debug: (optional) Set to True to print headers to stdout, and exit without
                  sending the upload request.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    :returns: A list of :py:class:`requests.Response` objects.
    """
    item = get_item(identifier, **get_item_kwargs)
    return item.upload(files,
                       metadata=metadata,
                       headers=headers,
                       access_key=access_key,
                       secret_key=secret_key,
                       queue_derive=queue_derive,
                       verbose=verbose,
                       verify=verify,
                       checksum=checksum,
                       delete=delete,
                       retries=retries,
                       retries_sleep=retries_sleep,
                       debug=debug,
                       request_kwargs=request_kwargs)


def download(identifier,
             files=None,
             formats=None,
             glob_pattern=None,
             dry_run=None,
             verbose=None,
             silent=None,
             ignore_existing=None,
             checksum=None,
             destdir=None,
             no_directory=None,
             retries=None,
             item_index=None,
             ignore_errors=None,
             on_the_fly=None,
             return_responses=None,
             **get_item_kwargs):
    """Download files from an item.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: (optional) Only return files matching the given file names.

    :param formats: (optional) Only return files matching the given formats.

    :type glob_pattern: str
    :param glob_pattern: (optional) Only return files matching the given glob pattern.

    :type dry_run: bool
    :param dry_run: (optional) Print URLs to files to stdout rather than downloading
                    them.

    :type verbose: bool
    :param verbose: (optional) Turn on verbose output.

    :type silent: bool
    :param silent: (optional) Suppress all output.

    :type ignore_existing: bool
    :param ignore_existing: (optional) Skip files that already exist
                            locally.

    :type checksum: bool
    :param checksum: (optional) Skip downloading file based on checksum.

    :type destdir: str
    :param destdir: (optional) The directory to download files to.

    :type no_directory: bool
    :param no_directory: (optional) Download files to current working
                         directory rather than creating an item directory.

    :type retries: int
    :param retries: (optional) The number of times to retry on failed
                    requests.

    :type item_index: int
    :param item_index: (optional) The index of the item for displaying
                       progress in bulk downloads.

    :type ignore_errors: bool
    :param ignore_errors: (optional) Don't fail if a single file fails to
                          download, continue to download other files.

    :type on_the_fly: bool
    :param on_the_fly: (optional) Download on-the-fly files (i.e. derivative EPUB,
                       MOBI, DAISY files).

    :type return_responses: bool
    :param return_responses: (optional) Rather than downloading files to disk, return
                             a list of response objects.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    :rtype: bool
    :returns: True if all files were downloaded successfully.
    """
    item = get_item(identifier, **get_item_kwargs)
    r = item.download(files=files,
                      formats=formats,
                      glob_pattern=glob_pattern,
                      dry_run=dry_run,
                      verbose=verbose,
                      silent=silent,
                      ignore_existing=ignore_existing,
                      checksum=checksum,
                      destdir=destdir,
                      no_directory=no_directory,
                      retries=retries,
                      item_index=item_index,
                      ignore_errors=ignore_errors,
                      on_the_fly=on_the_fly,
                      return_responses=return_responses)
    return r


def delete(identifier,
           files=None,
           formats=None,
           glob_pattern=None,
           cascade_delete=None,
           access_key=None,
           secret_key=None,
           verbose=None,
           debug=None, **kwargs):
    """Delete files from an item. Note: Some system files, such as <itemname>_meta.xml,
    cannot be deleted.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: (optional) Only return files matching the given filenames.

    :param formats: (optional) Only return files matching the given formats.

    :type glob_pattern: str
    :param glob_pattern: (optional) Only return files matching the given glob pattern.

    :type cascade_delete: bool
    :param cascade_delete: (optional) Also deletes files derived from the file, and files
                           the filewas derived from.

    :type access_key: str
    :param access_key: (optional) IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: (optional) IA-S3 secret_key to use when making the given request.

    :type verbose: bool
    :param verbose: Print actions to stdout.

    :type debug: bool
    :param debug: (optional) Set to True to print headers to stdout and exit exit without
                  sending the delete request.
    """
    files = get_files(identifier, files, formats, glob_pattern, **kwargs)

    responses = []
    for f in files:
        r = f.delete(cascade_delete=cascade_delete,
                     access_key=access_key,
                     secret_key=secret_key,
                     verbose=verbose,
                     debug=debug)
        responses.append(r)
    return responses


def get_tasks(identifier=None,
              task_ids=None,
              task_type=None,
              params=None,
              config=None,
              config_file=None,
              verbose=None,
              archive_session=None,
              http_adapter_kwargs=None,
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
    if not archive_session:
        archive_session = get_session(config, config_file, http_adapter_kwargs)
    return archive_session.get_tasks(identifier=identifier,
                                     task_ids=task_ids,
                                     params=params,
                                     config=config,
                                     verbose=verbose,
                                     request_kwargs=request_kwargs)


def search_items(query,
                 fields=None,
                 sorts=None,
                 params=None,
                 archive_session=None,
                 config=None,
                 config_file=None,
                 http_adapter_kwargs=None,
                 request_kwargs=None,
                 max_retries=None):
    """Search for items on Archive.org.

    :type query: str
    :param query: The Archive.org search query to yield results for. Refer to
                  https://archive.org/advancedsearch.php#raw for help formatting your
                  query.

    :type fields: list
    :param fields: (optional) The metadata fields to return in the search results.

    :type params: dict
    :param params: (optional) The URL parameters to send with each request sent to the
                   Archive.org Advancedsearch Api.

    :type config: dict
    :param secure: (optional) Configuration options for session.

    :type config_file: str
    :param config_file: (optional) A path to a config file used to configure your session.

    :type http_adapter_kwargs: dict
    :param http_adapter_kwargs: (optional) Keyword arguments that
                                :py:class:`requests.adapters.HTTPAdapter` takes.

    :type request_kwargs: dict
    :param request_kwargs: (optional) Keyword arguments that
                           :py:class:`requests.Request` takes.

    :type max_retries: int, object
    :param max_retries: The number of times to retry a failed request.
                        This can also be an `urllib3.Retry` object.
                        If you need more control (e.g. `status_forcelist`), use a
                        `ArchiveSession` object, and mount your own adapter after the
                        session object has been initialized. For example::

                        >>> s = get_session()
                        >>> s.mount_http_adapter()
                        >>> search_results = s.search_items('nasa')

                        See :meth:`ArchiveSession.mount_http_adapter`
                        for more details.

    :returns: A :class:`Search` object, yielding search results.
    """
    if not archive_session:
        archive_session = get_session(config, config_file, http_adapter_kwargs)
    return archive_session.search_items(query,
                                        fields=fields,
                                        sorts=sorts,
                                        params=params,
                                        request_kwargs=request_kwargs,
                                        max_retries=max_retries)


def configure(username=None, password=None, config_file=None):
    """Configure internetarchive with your Archive.org credentials.

    :type username: str
    :param username: The email address associated with your Archive.org account.

    :type password: str
    :param password: Your Archive.org password.

    Usage:
        >>> from internetarchive import configure
        >>> configure('user@example.com', 'password')
    """
    username = input('Email address: ') if not username else username
    password = getpass('Password: ') if not password else password
    config_file_path = config_module.write_config_file(username, password, config_file)
    return config_file_path


def get_username(access_key, secret_key):
    """Returns an Archive.org username given an IA-S3 key pair.

    :type access_key: str
    :param access_key: IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: IA-S3 secret_key to use when making the given request.
    """
    j = get_user_info(access_key, secret_key)
    return j.get('username')


def get_user_info(access_key, secret_key):
    """Returns details about an Archive.org user given an IA-S3 key pair.

    :type access_key: str
    :param access_key: IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: IA-S3 secret_key to use when making the given request.
    """
    u = 'https://s3.us.archive.org'
    p = dict(check_auth=1)
    r = requests.get(u, params=p, auth=auth.S3Auth(access_key, secret_key))
    r.raise_for_status()
    j = r.json()
    if j.get('error'):
        raise AuthenticationError(j.get('error'))
    else:
        return j
