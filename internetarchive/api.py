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
internetarchive.api
~~~~~~~~~~~~~~~~~~~

This module implements the Internetarchive API.

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

from getpass import getpass
from typing import Iterable, Mapping, MutableMapping

import requests
from urllib3 import Retry

from internetarchive import auth, catalog, files, item, search, session
from internetarchive import config as config_module
from internetarchive.exceptions import AuthenticationError


def get_session(
    config: Mapping | None = None,
    config_file: str | None = None,
    debug: bool = False,
    http_adapter_kwargs: MutableMapping | None = None,
) -> session.ArchiveSession:
    """Return a new :class:`ArchiveSession` object. The :class:`ArchiveSession`
    object is the main interface to the ``internetarchive`` lib. It allows you to
    persist certain parameters across tasks.

    :param config: A dictionary used to configure your session.

    :param config_file: A path to a config file used to configure your session.

    :param debug: To be passed on to this session's method calls.

    :param http_adapter_kwargs: Keyword arguments that
                                :py:class:`requests.adapters.HTTPAdapter` takes.

    :returns: To persist certain parameters across tasks.

    Usage:

        >>> from internetarchive import get_session
        >>> config = {'s3': {'access': 'foo', 'secret': 'bar'}}
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
    return session.ArchiveSession(config, config_file or "", debug, http_adapter_kwargs)


def get_item(
    identifier: str,
    config: Mapping | None = None,
    config_file: str | None = None,
    archive_session: session.ArchiveSession | None = None,
    debug: bool = False,
    http_adapter_kwargs: MutableMapping | None = None,
    request_kwargs: MutableMapping | None = None,
) -> item.Item:
    """Get an :class:`Item` object.

    :param identifier: The globally unique Archive.org item identifier.

    :param config: A dictionary used to configure your session.

    :param config_file: A path to a config file used to configure your session.

    :param archive_session: An :class:`ArchiveSession` object can be provided
                            via the ``archive_session`` parameter.

    :param debug: To be passed on to get_session().

    :param http_adapter_kwargs: Keyword arguments that
                                :py:class:`requests.adapters.HTTPAdapter` takes.

    :param request_kwargs: Keyword arguments that
                           :py:class:`requests.Request` takes.

    :returns: The Item that fits the criteria.

    Usage:
        >>> from internetarchive import get_item
        >>> item = get_item('nasa')
        >>> item.item_size
        121084
    """
    if not archive_session:
        archive_session = get_session(config, config_file, debug, http_adapter_kwargs)
    return archive_session.get_item(identifier, request_kwargs=request_kwargs)


def get_files(
    identifier: str,
    files: files.File | list[files.File] | None = None,
    formats: str | list[str] | None = None,
    glob_pattern: str | None = None,
    exclude_pattern: str | None = None,
    on_the_fly: bool = False,
    **get_item_kwargs,
) -> list[files.File]:
    r"""Get :class:`File` objects from an item.

    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: Only return files matching the given filenames.

    :param formats: Only return files matching the given formats.

    :param glob_pattern: Only return files matching the given glob pattern.

    :param exclude_pattern: Exclude files matching the given glob pattern.

    :param on_the_fly: Include on-the-fly files (i.e. derivative EPUB,
                       MOBI, DAISY files).

    :param \*\*get_item_kwargs: Arguments that ``get_item()`` takes.

    :returns: Files from an item.

    Usage:
        >>> from internetarchive import get_files
        >>> fnames = [f.name for f in get_files('nasa', glob_pattern='*xml')]
        >>> print(fnames)
        ['nasa_reviews.xml', 'nasa_meta.xml', 'nasa_files.xml']
    """
    item = get_item(identifier, **get_item_kwargs)
    return item.get_files(files, formats, glob_pattern, exclude_pattern, on_the_fly)


def modify_metadata(
    identifier: str,
    metadata: Mapping,
    target: str | None = None,
    append: bool = False,
    append_list: bool = False,
    priority: int = 0,
    access_key: str | None = None,
    secret_key: str | None = None,
    debug: bool = False,
    request_kwargs: Mapping | None = None,
    **get_item_kwargs,
) -> requests.Request | requests.Response:
    r"""Modify the metadata of an existing item on Archive.org.

    :param identifier: The globally unique Archive.org identifier for a given item.

    :param metadata: Metadata used to update the item.

    :param target: The metadata target to update. Defaults to `metadata`.

    :param append: set to True to append metadata values to current values
                   rather than replacing. Defaults to ``False``.

    :param append_list: Append values to an existing multi-value
                        metadata field. No duplicate values will be added.

    :param priority: Set task priority.

    :param access_key: IA-S3 access_key to use when making the given request.

    :param secret_key: IA-S3 secret_key to use when making the given request.

    :param debug: set to True to return a :class:`requests.Request <Request>`
                  object instead of sending request. Defaults to ``False``.

    :param \*\*get_item_kwargs: Arguments that ``get_item`` takes.

    :returns: A Request if debug else a Response.
    """
    item = get_item(identifier, **get_item_kwargs)
    return item.modify_metadata(
        metadata,
        target=target,
        append=append,
        append_list=append_list,
        priority=priority,
        access_key=access_key,
        secret_key=secret_key,
        debug=debug,
        request_kwargs=request_kwargs,
        refresh=False
    )


def upload(
    identifier: str,
    files,
    metadata: Mapping | None = None,
    headers: dict | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    queue_derive=None,
    verbose: bool = False,
    verify: bool = False,
    checksum: bool = False,
    delete: bool = False,
    retries: int | None = None,
    retries_sleep: int | None = None,
    debug: bool = False,
    validate_identifier: bool = False,
    request_kwargs: dict | None = None,
    **get_item_kwargs,
) -> list[requests.Request | requests.Response]:
    r"""Upload files to an item. The item will be created if it does not exist.

    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: The filepaths or file-like objects to upload. This value can be an
                  iterable or a single file-like object or string.

    :param metadata: Metadata used to create a new item. If the item already
                     exists, the metadata will not be updated -- use ``modify_metadata``.

    :param headers: Add additional HTTP headers to the request.

    :param access_key: IA-S3 access_key to use when making the given request.

    :param secret_key: IA-S3 secret_key to use when making the given request.

    :param queue_derive: Set to False to prevent an item from being derived
                         after upload.

    :param verbose: Display upload progress.

    :param verify: Verify local MD5 checksum matches the MD5 checksum of the
                   file received by IAS3.

    :param checksum: Skip uploading files based on checksum.

    :param delete: Delete local file after the upload has been successfully
                   verified.

    :param retries: Number of times to retry the given request if S3 returns a
                    503 SlowDown error.

    :param retries_sleep: Amount of time to sleep between ``retries``.

    :param debug: Set to True to print headers to stdout, and exit without
                  sending the upload request.

    :param validate_identifier: Set to True to validate the identifier before
                                uploading the file.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    :returns: A list Requests if debug else a list of Responses.
    """
    item = get_item(identifier, **get_item_kwargs)
    return item.upload(
        files,
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
        validate_identifier=validate_identifier,
        request_kwargs=request_kwargs,
    )


def download(
    identifier: str,
    files: files.File | list[files.File] | None = None,
    formats: str | list[str] | None = None,
    glob_pattern: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    ignore_existing: bool = False,
    checksum: bool = False,
    destdir: str | None = None,
    no_directory: bool = False,
    retries: int | None = None,
    item_index: int | None = None,
    ignore_errors: bool = False,
    on_the_fly: bool = False,
    return_responses: bool = False,
    no_change_timestamp: bool = False,
    timeout: int | float | tuple[int, float] | None = None,
    **get_item_kwargs,
) -> list[requests.Request | requests.Response]:
    r"""Download files from an item.

    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: Only return files matching the given file names.

    :param formats: Only return files matching the given formats.

    :param glob_pattern: Only return files matching the given glob pattern.

    :param dry_run: Print URLs to files to stdout rather than downloading
                    them.

    :param verbose: Turn on verbose output.

    :param ignore_existing: Skip files that already exist locally.

    :param checksum: Skip downloading file based on checksum.

    :param destdir: The directory to download files to.

    :param no_directory: Download files to current working
                         directory rather than creating an item directory.

    :param retries: The number of times to retry on failed
                    requests.

    :param item_index: The index of the item for displaying
                       progress in bulk downloads.

    :param ignore_errors: Don't fail if a single file fails to
                          download, continue to download other files.

    :param on_the_fly: Download on-the-fly files (i.e. derivative EPUB,
                       MOBI, DAISY files).

    :param return_responses: Rather than downloading files to disk, return
                             a list of response objects.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    :returns: A list Requests if debug else a list of Responses.
    """
    item = get_item(identifier, **get_item_kwargs)
    r = item.download(
        files=files,
        formats=formats,
        glob_pattern=glob_pattern,
        dry_run=dry_run,
        verbose=verbose,
        ignore_existing=ignore_existing,
        checksum=checksum,
        destdir=destdir,
        no_directory=no_directory,
        retries=retries,
        item_index=item_index,
        ignore_errors=ignore_errors,
        on_the_fly=on_the_fly,
        return_responses=return_responses,
        no_change_timestamp=no_change_timestamp,
        timeout=timeout,
    )
    return r


def delete(
    identifier: str,
    files: files.File | list[files.File] | None = None,
    formats: str | list[str] | None = None,
    glob_pattern: str | None = None,
    cascade_delete: bool = False,
    access_key: str | None = None,
    secret_key: str | None = None,
    verbose: bool = False,
    debug: bool = False,
    **kwargs,
) -> list[requests.Request | requests.Response]:
    """Delete files from an item. Note: Some system files, such as <itemname>_meta.xml,
    cannot be deleted.

    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: Only return files matching the given filenames.

    :param formats: Only return files matching the given formats.

    :param glob_pattern: Only return files matching the given glob pattern.

    :param cascade_delete: Delete all files associated with the specified file,
                           including upstream derivatives and the original.

    :param access_key: IA-S3 access_key to use when making the given request.

    :param secret_key: IA-S3 secret_key to use when making the given request.

    :param verbose: Print actions to stdout.

    :param debug: Set to True to print headers to stdout and exit exit without
                  sending the delete request.

    :returns: A list Requests if debug else a list of Responses
    """
    _files = get_files(identifier, files, formats, glob_pattern, **kwargs)

    responses = []
    for f in _files:
        r = f.delete(
            cascade_delete=cascade_delete,
            access_key=access_key,
            secret_key=secret_key,
            verbose=verbose,
            debug=debug,
        )
        responses.append(r)
    return responses


def get_tasks(
    identifier: str = "",
    params: dict | None = None,
    config: Mapping | None = None,
    config_file: str | None = None,
    archive_session: session.ArchiveSession | None = None,
    http_adapter_kwargs: MutableMapping | None = None,
    request_kwargs: MutableMapping | None = None,
) -> set[catalog.CatalogTask]:
    """Get tasks from the Archive.org catalog.

    :param identifier: The Archive.org identifier for which to retrieve tasks for.

    :param params: The URL parameters to send with each request sent to the
                   Archive.org catalog API.

    :returns: A set of :class:`CatalogTask` objects.
    """
    if not archive_session:
        archive_session = get_session(config, config_file, False, http_adapter_kwargs)
    return archive_session.get_tasks(
        identifier=identifier, params=params, request_kwargs=request_kwargs
    )


def search_items(
    query: str,
    fields: Iterable | None = None,
    sorts=None,
    params: Mapping | None = None,
    full_text_search: bool = False,
    dsl_fts: bool = False,
    archive_session: session.ArchiveSession | None = None,
    config: Mapping | None = None,
    config_file: str | None = None,
    http_adapter_kwargs: MutableMapping | None = None,
    request_kwargs: Mapping | None = None,
    max_retries: int | Retry | None = None,
) -> search.Search:
    """Search for items on Archive.org.

    :param query: The Archive.org search query to yield results for. Refer to
                  https://archive.org/advancedsearch.php#raw for help formatting your
                  query.

    :param fields: The metadata fields to return in the search results.

    :param params: The URL parameters to send with each request sent to the
                   Archive.org Advancedsearch Api.

    :param full_text_search: Beta support for querying the archive.org
                             Full Text Search API [default: False].

    :param dsl_fts: Beta support for querying the archive.org Full Text
                    Search API in dsl (i.e. do not prepend ``!L `` to the
                    ``full_text_search`` query [default: False].

    :param secure: Configuration options for session.

    :param config_file: A path to a config file used to configure your session.

    :param http_adapter_kwargs: Keyword arguments that
                                :py:class:`requests.adapters.HTTPAdapter` takes.

    :param request_kwargs: Keyword arguments that
                           :py:class:`requests.Request` takes.

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
        archive_session = get_session(config, config_file, False, http_adapter_kwargs)
    return archive_session.search_items(
        query,
        fields=fields,
        sorts=sorts,
        params=params,
        full_text_search=full_text_search,
        dsl_fts=dsl_fts,
        request_kwargs=request_kwargs,
        max_retries=max_retries,
    )


def configure(  # nosec: hardcoded_password_default
    username: str = "",
    password: str = "",
    config_file: str = "",
    host: str = "archive.org",
) -> str:
    """Configure internetarchive with your Archive.org credentials.

    :param username: The email address associated with your Archive.org account.

    :param password: Your Archive.org password.

    :returns: The config file path.

    Usage:
        >>> from internetarchive import configure
        >>> configure('user@example.com', 'password')
    """
    auth_config = config_module.get_auth_config(
        username or input("Email address: "),
        password or getpass("Password: "),
        host,
    )
    config_file_path = config_module.write_config_file(auth_config, config_file)
    return config_file_path


def get_username(access_key: str, secret_key: str) -> str:
    """Returns an Archive.org username given an IA-S3 key pair.

    :param access_key: IA-S3 access_key to use when making the given request.

    :param secret_key: IA-S3 secret_key to use when making the given request.

    :returns: The username.
    """
    j = get_user_info(access_key, secret_key)
    return j.get("username", "")


def get_user_info(access_key: str, secret_key: str) -> dict[str, str]:
    """Returns details about an Archive.org user given an IA-S3 key pair.

    :param access_key: IA-S3 access_key to use when making the given request.

    :param secret_key: IA-S3 secret_key to use when making the given request.

    :returns: Archive.org use info.
    """
    u = "https://s3.us.archive.org"
    p = {"check_auth": 1}
    r = requests.get(u, params=p, auth=auth.S3Auth(access_key, secret_key), timeout=10)
    r.raise_for_status()
    j = r.json()
    if j.get("error"):
        raise AuthenticationError(j.get("error"))
    else:
        return j
