#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2021 Internet Archive
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
internetarchive.item
~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2021 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import io
import math
import os
import sys
from copy import deepcopy
from fnmatch import fnmatch
from functools import total_ordering
from logging import getLogger
from time import sleep
from typing import Mapping, MutableMapping
from urllib.parse import quote
from xml.parsers.expat import ExpatError

from requests import Request, Response
from requests.exceptions import HTTPError
from tqdm import tqdm

from internetarchive import catalog
from internetarchive.auth import S3Auth
from internetarchive.files import File
from internetarchive.iarequest import MetadataRequest, S3Request
from internetarchive.utils import (
    IdentifierListAsItems,
    IterableToFileAdapter,
    chunk_generator,
    get_file_size,
    get_md5,
    get_s3_xml_text,
    is_dir,
    iter_directory,
    json,
    norm_filepath,
    recursive_file_count_and_size,
    validate_s3_identifier,
)

log = getLogger(__name__)


@total_ordering
class BaseItem:
    EXCLUDED_ITEM_METADATA_KEYS = ('workable_servers', 'server')

    def __init__(
        self,
        identifier: str | None = None,
        item_metadata: Mapping | None = None,
    ):
        # Default attributes.
        self.identifier = identifier
        self.item_metadata = item_metadata or {}
        self.exists = False

        # Archive.org metadata attributes.
        self.metadata: dict = {}
        self.files: list[dict] = []
        self.created = None
        self.d1 = None
        self.d2 = None
        self.dir = None
        self.files_count = None
        self.item_size = None
        self.reviews: list = []
        self.server = None
        self.uniq = None
        self.updated = None
        self.tasks = None
        self.is_dark = None

        # Load item.
        self.load()

    def __repr__(self) -> str:
        notloaded = ', item_metadata={}' if not self.exists else ''
        return f'{self.__class__.__name__}(identifier={self.identifier!r}{notloaded})'

    def load(self, item_metadata: Mapping | None = None) -> None:
        if item_metadata:
            self.item_metadata = item_metadata

        self.exists = bool(self.item_metadata)

        for key in self.item_metadata:
            setattr(self, key, self.item_metadata[key])

        if not self.identifier:
            self.identifier = self.metadata.get('identifier')

        mc = self.metadata.get('collection', [])
        # TODO: The `type: ignore` on the following line should be removed.  See #518
        self.collection = IdentifierListAsItems(mc, self.session)  # type: ignore

    def __eq__(self, other) -> bool:
        return (self.item_metadata == other.item_metadata
                or (self.item_metadata.keys() == other.item_metadata.keys()
                    and all(self.item_metadata[x] == other.item_metadata[x]
                            for x in self.item_metadata
                            if x not in self.EXCLUDED_ITEM_METADATA_KEYS)))

    def __le__(self, other) -> bool:
        return self.identifier <= other.identifier

    def __hash__(self) -> int:
        without_excluded_keys = {
            k: v for k, v in self.item_metadata.items()
            if k not in self.EXCLUDED_ITEM_METADATA_KEYS}
        return hash(json.dumps(without_excluded_keys,
                               sort_keys=True, check_circular=False))  # type: ignore


class Item(BaseItem):
    """This class represents an archive.org item. Generally this class
    should not be used directly, but rather via the
    ``internetarchive.get_item()`` function::

        >>> from internetarchive import get_item
        >>> item = get_item('stairs')
        >>> print(item.metadata)

    Or to modify the metadata for an item::

        >>> metadata = {'title': 'The Stairs'}
        >>> item.modify_metadata(metadata)
        >>> print(item.metadata['title'])
        'The Stairs'

    This class also uses IA's S3-like interface to upload files to an
    item. You need to supply your IAS3 credentials in environment
    variables in order to upload::

        >>> item.upload('myfile.tar', access_key='Y6oUrAcCEs4sK8ey',
        ...                           secret_key='youRSECRETKEYzZzZ')
        True

    You can retrieve S3 keys here: `https://archive.org/account/s3.php
    <https://archive.org/account/s3.php>`__
    """

    def __init__(
        self,
        archive_session,
        identifier: str,
        item_metadata: Mapping | None = None,
    ):
        """
        :param archive_session: :class:`ArchiveSession <ArchiveSession>`

        :param identifier: The globally unique Archive.org identifier for this item.

                           An identifier is composed of any unique combination of
                           alphanumeric characters, underscore ( _ ) and dash ( - ). While
                           there are no official limits it is strongly suggested that they
                           be between 5 and 80 characters in length. Identifiers must be
                           unique across the entirety of Internet Archive, not simply
                           unique within a single collection.

                           Once defined an identifier can not be changed. It will travel
                           with the item or object and is involved in every manner of
                           accessing or referring to the item.

        :param item_metadata: The Archive.org item metadata used to initialize
                              this item.  If no item metadata is provided, it will be
                              retrieved from Archive.org using the provided identifier.
        """
        self.session = archive_session
        super().__init__(identifier, item_metadata)

        self.urls = Item.URLs(self)

        if self.metadata.get('title'):
            # A copyable link to the item, in MediaWiki format
            details = self.urls.details  # type: ignore
            self.wikilink = f'* [{details} {self.identifier}] -- {self.metadata["title"]}'

    class URLs:
        def __init__(self, itm_obj):
            self._itm_obj = itm_obj
            self._paths = []
            self._make_URL('details')
            self._make_URL('metadata')
            self._make_URL('download')
            self._make_URL('history')
            self._make_URL('edit')
            self._make_URL('editxml')
            self._make_URL('manage')
            if self._itm_obj.metadata.get('mediatype') == 'collection':
                self._make_tab_URL('about')
                self._make_tab_URL('collection')

        def _make_tab_URL(self, tab: str) -> None:
            """Make URLs for the separate tabs of Collections details page."""
            self._make_URL(tab, self.details + f'&tab={tab}')  # type: ignore

        DEFAULT_URL_FORMAT = ('{0.session.protocol}//{0.session.host}'
                              '/{path}/{0.identifier}')

        def _make_URL(self, path: str, url_format: str = DEFAULT_URL_FORMAT) -> None:
            setattr(self, path, url_format.format(self._itm_obj, path=path))
            self._paths.append(path)

        def __str__(self) -> str:
            return f'URLs ({", ".join(self._paths)}) for {self._itm_obj.identifier}'

    def refresh(self, item_metadata: Mapping | None = None, **kwargs) -> None:
        if not item_metadata:
            item_metadata = self.session.get_metadata(self.identifier, **kwargs)
        self.load(item_metadata)

    def identifier_available(self) -> bool:
        """Check if the item identifier is available for creating a
        new item.

        :return: `True` if identifier is available, or `False` if it is
                 not available.
        """
        url = f'{self.session.protocol}//{self.session.host}/services/check_identifier.php'
        params = {'output': 'json', 'identifier': self.identifier}
        response = self.session.get(url, params=params)
        availability = response.json()['code']
        return availability == 'available'

    def get_task_summary(
        self,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> dict:
        """Get a summary of the item's pending tasks.

        :param params: Params to send with your request.

        :returns: A summary of the item's pending tasks.
        """
        return self.session.get_tasks_summary(self.identifier, params, request_kwargs)

    def no_tasks_pending(
        self,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> bool:
        """Check if there is any pending task for the item.

        :param params: Params to send with your request.

        :returns: `True` if no tasks are pending, otherwise `False`.
        """
        return all(x == 0 for x in self.get_task_summary(params, request_kwargs).values())

    def get_all_item_tasks(
        self,
        params: dict | None = None,
        request_kwargs: Mapping | None = None,
    ) -> list[catalog.CatalogTask]:
        """Get a list of all tasks for the item, pending and complete.

        :param params: Query parameters, refer to
                       `Tasks API
                       <https://archive.org/services/docs/api/tasks.html>`_
                       for available parameters.

        :param request_kwargs: Keyword arguments that
                               :py:func:`requests.get` takes.

        :returns: A list of all tasks for the item, pending and complete.
        """
        params = params or {}
        params.update({'catalog': 1, 'history': 1})
        return self.session.get_tasks(self.identifier, params, request_kwargs)

    def get_history(
        self,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> list[catalog.CatalogTask]:
        """Get a list of completed catalog tasks for the item.

        :param params: Params to send with your request.

        :returns: A list of completed catalog tasks for the item.
        """
        return list(self.session.iter_history(self.identifier, params, request_kwargs))

    def get_catalog(
        self,
        params: Mapping | None = None,
        request_kwargs: Mapping | None = None,
    ) -> list[catalog.CatalogTask]:
        """Get a list of pending catalog tasks for the item.

        :param params: Params to send with your request.

        :returns: A list of pending catalog tasks for the item.
        """
        return list(self.session.iter_catalog(self.identifier, params, request_kwargs))

    def derive(self,
               priority: int = 0,
               remove_derived: str | None = None,
               reduced_priority: bool = False,
               data: MutableMapping | None = None,
               headers: Mapping | None = None,
               request_kwargs: Mapping | None = None) -> Response:
        """Derive an item.

        :param priority: Task priority from 10 to -10 [default: 0]

        :param remove_derived: You can use wildcards ("globs")
                               to only remove *some* prior derivatives.
                               For example, "*" (typed without the
                               quotation marks) specifies that all
                               derivatives (in the item's top directory)
                               are to be rebuilt. "*.mp4" specifies that
                               all "*.mp4" deriviatives are to be rebuilt.
                               "{*.gif,*thumbs/*.jpg}" specifies that all
                               GIF and thumbs are to be rebuilt.

        :param reduced_priority: Submit your derive at a lower priority.
                                 This option is helpful to get around rate-limiting.
                                 Your task will more likely be accepted, but it might
                                 not run for a long time. Note that you still may be
                                 subject to rate-limiting.

        :returns: :class:`requests.Response`
        """
        data = data or {}

        if remove_derived is not None:
            if not data.get('args'):
                data['args'] = {'remove_derived': remove_derived}
            else:
                data['args'].update({'remove_derived': remove_derived})

        r = self.session.submit_task(self.identifier,
                                     'derive.php',
                                     priority=priority,
                                     data=data,
                                     headers=headers,
                                     reduced_priority=reduced_priority,
                                     request_kwargs=request_kwargs)
        r.raise_for_status()
        return r

    def fixer(self,
              ops: list | str | None = None,
              priority: int | str | None = None,
              reduced_priority: bool = False,
              data: MutableMapping | None = None,
              headers: Mapping | None = None,
              request_kwargs: Mapping | None = None) -> Response:
        """Submit a fixer task on an item.

        :param ops: The fixer operation(s) to run on the item
                    [default: noop].

        :param priority: The task priority.

        :param reduced_priority: Submit your derive at a lower priority.
                                 This option is helpful to get around rate-limiting.
                                 Your task will more likely be accepted, but it might
                                 not run for a long time. Note that you still may be
                                 subject to rate-limiting. This is different than
                                 ``priority`` in that it will allow you to possibly
                                 avoid rate-limiting.

        :param data: Additional parameters to submit with
                     the task.

        :returns: :class:`requests.Response`
        """
        data = data or {}

        ops = ops or ['noop']
        if not isinstance(ops, (list, tuple, set)):
            ops = [ops]
        data['args'] = data.get('args') or {}
        for op in ops:
            data['args'][op] = '1'

        r = self.session.submit_task(self.identifier,
                                     'fixer.php',
                                     priority=priority,
                                     data=data,
                                     headers=headers,
                                     reduced_priority=reduced_priority,
                                     request_kwargs=request_kwargs)
        r.raise_for_status()
        return r

    def undark(self,
               comment: str,
               priority: int | str | None = None,
               reduced_priority: bool = False,
               data: Mapping | None = None,
               request_kwargs: Mapping | None = None) -> Response:
        """Undark the item.

        :param comment: The curation comment explaining reason for
                        undarking item

        :param priority: The task priority.

        :param reduced_priority: Submit your derive at a lower priority.
                                 This option is helpful to get around rate-limiting.
                                 Your task will more likely be accepted, but it might
                                 not run for a long time. Note that you still may be
                                 subject to rate-limiting. This is different than
                                 ``priority`` in that it will allow you to possibly
                                 avoid rate-limiting.

        :param data: Additional parameters to submit with
                     the task.

        :returns: :class:`requests.Response`
        """
        r = self.session.submit_task(self.identifier,
                                     'make_undark.php',
                                     comment=comment,
                                     priority=priority,
                                     data=data,
                                     reduced_priority=reduced_priority,
                                     request_kwargs=request_kwargs)
        r.raise_for_status()
        return r

    # TODO: dark and undark have different order for data and reduced_pripoity
    def dark(self,
             comment: str,
             priority: int | str | None = None,
             data: Mapping | None = None,
             reduced_priority: bool = False,
             request_kwargs: Mapping | None = None) -> Response:
        """Dark the item.

        :param comment: The curation comment explaining reason for
                        darking item

        :param priority: The task priority.

        :param reduced_priority: Submit your derive at a lower priority.
                                 This option is helpful to get around rate-limiting.
                                 Your task will more likely be accepted, but it might
                                 not run for a long time. Note that you still may be
                                 subject to rate-limiting. This is different than
                                 ``priority`` in that it will allow you to possibly
                                 avoid rate-limiting.

        :param data: Additional parameters to submit with
                     the task.

        :returns: :class:`requests.Response`
        """
        r = self.session.submit_task(self.identifier,
                                     'make_dark.php',
                                     comment=comment,
                                     priority=priority,
                                     data=data,
                                     reduced_priority=reduced_priority,
                                     request_kwargs=request_kwargs)
        r.raise_for_status()
        return r

    def get_review(self) -> Response:
        u = f'{self.session.protocol}//{self.session.host}/services/reviews.php'
        p = {'identifier': self.identifier}
        a = S3Auth(self.session.access_key, self.session.secret_key)
        r = self.session.get(u, params=p, auth=a)
        r.raise_for_status()
        return r

    def delete_review(self, username=None, screenname=None, itemname=None) -> Response:
        u = f'{self.session.protocol}//{self.session.host}/services/reviews.php'
        p = {'identifier': self.identifier}
        d = None
        if username:
            d = {'username': username}
        elif screenname:
            d = {'screenname': screenname}
        elif itemname:
            d = {'itemname': itemname}
        a = S3Auth(self.session.access_key, self.session.secret_key)
        r = self.session.delete(u, params=p, data=d, auth=a)
        r.raise_for_status()
        return r

    def review(self, title, body, stars=None) -> Response:
        u = f'{self.session.protocol}//{self.session.host}/services/reviews.php'
        p = {'identifier': self.identifier}
        d = {'title': title, 'body': body}
        if stars:
            d['stars'] = stars
        a = S3Auth(self.session.access_key, self.session.secret_key)
        r = self.session.post(u, params=p, data=json.dumps(d), auth=a)
        r.raise_for_status()
        return r

    def get_file(self, file_name: str, file_metadata: Mapping | None = None) -> File:
        """Get a :class:`File <File>` object for the named file.

        :param file_metadata: a dict of metadata for the
                              given file.

        :returns: An :class:`internetarchive.File <File>` object.
        """
        return File(self, file_name, file_metadata)

    def get_files(self,
                  files: File | list[File] | None = None,
                  formats: str | list[str] | None = None,
                  glob_pattern: str | None = None,
                  exclude_pattern: str | None = None,
                  on_the_fly: bool = False):
        files = files or []
        formats = formats or []
        exclude_pattern = exclude_pattern or ''
        on_the_fly = bool(on_the_fly)

        if not isinstance(files, (list, tuple, set)):
            files = [files]
        if not isinstance(formats, (list, tuple, set)):
            formats = [formats]

        item_files = deepcopy(self.files)
        # Add support for on-the-fly files (e.g. EPUB).
        if on_the_fly:
            otf_files = [
                ('EPUB', f'{self.identifier}.epub'),
                ('MOBI', f'{self.identifier}.mobi'),
                ('DAISY', f'{self.identifier}_daisy.zip'),
                ('MARCXML', f'{self.identifier}_archive_marc.xml'),
            ]
            for format, file_name in otf_files:
                item_files.append({'name': file_name, 'format': format, 'otf': True})

        if not any(k for k in [files, formats, glob_pattern]):
            for f in item_files:
                yield self.get_file(str(f.get('name')), file_metadata=f)

        for f in item_files:
            if f.get('name') in files:
                yield self.get_file(str(f.get('name')))
            elif f.get('format') in formats:
                yield self.get_file(str(f.get('name')))
            elif glob_pattern:
                if not isinstance(glob_pattern, list):
                    patterns = glob_pattern.split('|')
                else:
                    patterns = glob_pattern
                if not isinstance(exclude_pattern, list):
                    exclude_patterns = exclude_pattern.split('|')
                else:
                    exclude_patterns = exclude_pattern
                for p in patterns:
                    if fnmatch(f.get('name', ''), p):
                        if not any(fnmatch(f.get('name', ''), e) for e in exclude_patterns):
                            yield self.get_file(str(f.get('name')))

    def download(self,
                 files: File | list[File] | None = None,
                 formats: str | list[str] | None = None,
                 glob_pattern: str | None = None,
                 exclude_pattern: str | None = None,
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
                 ignore_history_dir: bool = False,
                 source: str | list[str] | None = None,
                 exclude_source: str | list[str] | None = None,
                 stdout: bool = False,
                 params: Mapping | None = None,
                 timeout: int | float | tuple[int, float] | None = None
                 ) -> list[Request | Response]:
        """Download files from an item.

        :param files: Only download files matching given file names.

        :param formats: Only download files matching the given
                        Formats.

        :param glob_pattern: Only download files matching the given
                             glob pattern.

        :param exclude_pattern: Exclude files whose filename matches the given
                                glob pattern.

        :param dry_run: Output download URLs to stdout, don't
                        download anything.

        :param verbose: Turn on verbose output.

        :param ignore_existing: Skip files that already exist
                                locally.

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

        :param no_change_timestamp: If True, leave the time stamp as the
                                    current time instead of changing it to that given in
                                    the original archive.

        :param source: Filter files based on their source value in files.xml
                       (i.e. `original`, `derivative`, `metadata`).

        :param exclude_source: Filter files based on their source value in files.xml
                               (i.e. `original`, `derivative`, `metadata`).

        :param params: URL parameters to send with
                       download request (e.g. `cnt=0`).

        :param ignore_history_dir: Do not download any files from the history
                                   dir. This param defaults to ``False``.

        :returns: True if if all files have been downloaded successfully.
        """
        dry_run = bool(dry_run)
        verbose = bool(verbose)
        ignore_existing = bool(ignore_existing)
        ignore_errors = bool(ignore_errors)
        checksum = bool(checksum)
        no_directory = bool(no_directory)
        return_responses = bool(return_responses)
        no_change_timestamp = bool(no_change_timestamp)
        ignore_history_dir = bool(ignore_history_dir)
        params = params or None
        if source:
            if not isinstance(source, list):
                source = [source]
        if exclude_source:
            if not isinstance(exclude_source, list):
                exclude_source = [exclude_source]
        if stdout:
            fileobj = os.fdopen(sys.stdout.fileno(), "wb", closefd=False)
            verbose = False
        else:
            fileobj = None

        if not dry_run:
            if item_index and verbose:
                print(f'{self.identifier} ({item_index}):', file=sys.stderr)
            elif item_index is None and verbose:
                print(f'{self.identifier}:', file=sys.stderr)

        if self.is_dark:
            msg = f'skipping {self.identifier}, item is dark'
            log.warning(msg)
            if verbose:
                print(f' {msg}', file=sys.stderr)
            return []
        elif self.metadata == {}:
            msg = f'skipping {self.identifier}, item does not exist.'
            log.warning(msg)
            if verbose:
                print(f' {msg}', file=sys.stderr)
            return []

        if files:
            files = self.get_files(files, on_the_fly=on_the_fly)
        else:
            files = self.get_files(on_the_fly=on_the_fly)
        if formats:
            files = self.get_files(formats=formats, on_the_fly=on_the_fly)
        if glob_pattern:
            files = self.get_files(
                glob_pattern=glob_pattern,
                exclude_pattern=exclude_pattern,
                on_the_fly=on_the_fly
            )
        if stdout:
            files = list(files)  # type: ignore

        errors = []
        downloaded = 0
        responses = []
        file_count = 0

        for f in files:  # type: ignore
            if ignore_history_dir is True:
                if f.name.startswith('history/'):
                    continue
            if source and not any(f.source == x for x in source):
                continue
            if exclude_source and any(f.source == x for x in exclude_source):
                continue
            file_count += 1
            if no_directory:
                path = f.name
            else:
                path = os.path.join(str(self.identifier), f.name)
            if dry_run:
                print(f.url)
                continue
            if stdout and file_count < len(files):  # type: ignore
                ors = True
            else:
                ors = False
            r = f.download(path, verbose, ignore_existing, checksum, destdir,
                           retries, ignore_errors, fileobj, return_responses,
                           no_change_timestamp, params, None, stdout, ors, timeout)
            if return_responses:
                responses.append(r)

            if r is False:
                errors.append(f.name)
            else:
                downloaded += 1

        if file_count == 0:
            msg = f'skipping {self.identifier}, no matching files found.'
            log.info(msg)
            if verbose:
                print(f' {msg}', file=sys.stderr)
            return []

        return responses if return_responses else errors

    def modify_metadata(self,
                        metadata: Mapping,
                        target: str | None = None,
                        append: bool = False,
                        expect: Mapping | None = None,
                        append_list: bool = False,
                        insert: bool = False,
                        priority: int = 0,
                        access_key: str | None = None,
                        secret_key: str | None = None,
                        debug: bool = False,
                        headers: Mapping | None = None,
                        request_kwargs: Mapping | None = None,
                        timeout: int | float | None = None,
                        refresh: bool = True) -> Request | Response:
        """Modify the metadata of an existing item on Archive.org.

        Note: The Metadata Write API does not yet comply with the
        latest Json-Patch standard. It currently complies with `version 02
        <https://tools.ietf.org/html/draft-ietf-appsawg-json-patch-02>`__.

        :param metadata: Metadata used to update the item.

        :param target: Set the metadata target to update.

        :param priority: Set task priority.

        :param append: Append value to an existing multi-value
                       metadata field.

        :param expect: Provide a dict of expectations to be tested
                       server-side before applying patch to item metadata.

        :param append_list: Append values to an existing multi-value
                            metadata field. No duplicate values will be added.

        :param refresh: Refresh the item metadata after the request.

        :returns: A Request if debug else a Response.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('mapi_test_item1')
            >>> md = {'new_key': 'new_value', 'foo': ['bar', 'bar2']}
            >>> item.modify_metadata(md)
        """
        append = bool(append)
        access_key = access_key or self.session.access_key
        secret_key = secret_key or self.session.secret_key
        debug = bool(debug)
        headers = headers or {}
        expect = expect or {}
        request_kwargs = request_kwargs or {}
        if timeout:
            request_kwargs["timeout"] = float(timeout)  # type: ignore
        else:
            request_kwargs["timeout"] = 60  # type: ignore

        _headers = self.session.headers.copy()
        _headers.update(headers)

        url = f'{self.session.protocol}//{self.session.host}/metadata/{self.identifier}'
        # TODO: currently files and metadata targets do not support dict's,
        # but they might someday?? refactor this check.
        source_metadata = self.item_metadata
        request = MetadataRequest(
            method='POST',
            url=url,
            metadata=metadata,
            headers=_headers,
            source_metadata=source_metadata,
            target=target,
            priority=priority,
            access_key=access_key,
            secret_key=secret_key,
            append=append,
            expect=expect,
            append_list=append_list,
            insert=insert)
        # Must use Session.prepare_request to make sure session settings
        # are used on request!
        prepared_request = request.prepare()
        if debug:
            return prepared_request
        resp = self.session.send(prepared_request, **request_kwargs)
        # Re-initialize the Item object with the updated metadata.
        if refresh:
            self.refresh()
        return resp

    # TODO: `list` parameter name shadows the Python builtin
    def remove_from_simplelist(self, parent, list) -> Response:
        """Remove item from a simplelist.

        :returns: :class:`requests.Response`
        """
        patch = {
            'op': 'delete',
            'parent': parent,
            'list': list,
        }
        data = {
            '-patch': json.dumps(patch),
            '-target': 'simplelists',
        }
        r = self.session.post(self.urls.metadata, data=data)  # type: ignore
        return r

    def upload_file(self, body,
                    key: str | None = None,
                    metadata: Mapping | None = None,
                    file_metadata: Mapping | None = None,
                    headers: dict | None = None,
                    access_key: str | None = None,
                    secret_key: str | None = None,
                    queue_derive: bool = False,
                    verbose: bool = False,
                    verify: bool = False,
                    checksum: bool = False,
                    delete: bool = False,
                    retries: int | None = None,
                    retries_sleep: int | None = None,
                    debug: bool = False,
                    validate_identifier: bool = False,
                    request_kwargs: MutableMapping | None = None,
                    set_scanner: bool = True) -> Request | Response:
        """Upload a single file to an item. The item will be created
        if it does not exist.

        :type body: Filepath or file-like object.
        :param body: File or data to be uploaded.

        :param key: Remote filename.

        :param metadata: Metadata used to create a new item.

        :param file_metadata: File-level metadata to add to
                              the files.xml entry for the file being
                              uploaded.

        :param headers: Add additional IA-S3 headers to request.

        :param queue_derive: Set to False to prevent an item from
                             being derived after upload.

        :param verify: Verify local MD5 checksum matches the MD5
                       checksum of the file received by IAS3.

        :param checksum: Skip based on checksum.

        :param delete: Delete local file after the upload has been
                       successfully verified.

        :param retries: Number of times to retry the given request
                        if S3 returns a 503 SlowDown error.

        :param retries_sleep: Amount of time to sleep between
                              ``retries``.

        :param verbose: Print progress to stdout.

        :param debug: Set to True to print headers to stdout, and
                      exit without sending the upload request.

        :param validate_identifier: Set to True to validate the identifier before
                                    uploading the file.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> item.upload_file('/path/to/image.jpg',
            ...                  key='photos/image1.jpg')
            True
        """
        # Set defaults.
        headers = headers or {}
        metadata = metadata or {}
        file_metadata = file_metadata or {}
        access_key = access_key or self.session.access_key
        secret_key = secret_key or self.session.secret_key
        queue_derive = bool(queue_derive)
        verbose = bool(verbose)
        verify = bool(verify)
        delete = bool(delete)
        # Set checksum after delete.
        checksum = delete or checksum
        retries = retries or 0
        retries_sleep = retries_sleep or 30
        debug = bool(debug)
        validate_identifier = bool(validate_identifier)
        request_kwargs = request_kwargs or {}
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 120
        md5_sum = None

        _headers = headers.copy()

        if not hasattr(body, 'read'):
            filename = body
            body = open(body, 'rb')
        else:
            filename = key or body.name

        size = get_file_size(body)

        # Support for uploading empty files.
        if size == 0:
            _headers['Content-Length'] = '0'

        if not _headers.get('x-archive-size-hint'):
            _headers['x-archive-size-hint'] = str(size)

        # Build IA-S3 URL.
        if validate_identifier:
            validate_s3_identifier(self.identifier or "")
        key = norm_filepath(filename).split('/')[-1] if key is None else key
        base_url = f'{self.session.protocol}//s3.us.archive.org/{self.identifier}'
        url = f'{base_url}/{quote(norm_filepath(key).lstrip("/").encode("utf-8"))}'

        # Skip based on checksum.
        if checksum:
            md5_sum = get_md5(body)
            ia_file = self.get_file(key)
            if (not self.tasks) and (ia_file) and (ia_file.md5 == md5_sum):
                log.info(f'{key} already exists: {url}')
                if verbose:
                    print(f' {key} already exists, skipping.', file=sys.stderr)
                if delete:
                    log.info(
                        f'{key} successfully uploaded to '
                        f'https://archive.org/download/{self.identifier}/{key} '
                        'and verified, deleting local copy')
                    body.close()
                    os.remove(filename)
                # Return an empty response object if checksums match.
                # TODO: Is there a better way to handle this?
                body.close()
                return Response()

        # require the Content-MD5 header when delete is True.
        if verify or delete:
            if not md5_sum:
                md5_sum = get_md5(body)
            _headers['Content-MD5'] = md5_sum

        def _build_request():
            body.seek(0, os.SEEK_SET)
            if verbose:
                try:
                    # hack to raise exception so we get some output for
                    # empty files.
                    if size == 0:
                        raise Exception

                    chunk_size = 1048576
                    expected_size = math.ceil(size / chunk_size)
                    chunks = chunk_generator(body, chunk_size)
                    progress_generator = tqdm(chunks,
                                              desc=f' uploading {key}',
                                              dynamic_ncols=True,
                                              total=expected_size,
                                              unit='MiB')
                    data = None
                    # pre_encode is needed because http doesn't know that it
                    # needs to encode a TextIO object when it's wrapped
                    # in the Iterator from tqdm.
                    # So, this FileAdapter provides pre-encoded output
                    data = IterableToFileAdapter(
                        progress_generator,
                        size,
                        pre_encode=isinstance(body, io.TextIOBase)
                    )
                except Exception:
                    print(f' uploading {key}', file=sys.stderr)
                    data = body
            else:
                data = body

            _headers.update(self.session.headers)
            request = S3Request(method='PUT',
                                url=url,
                                headers=_headers,
                                data=data,
                                metadata=metadata,
                                file_metadata=file_metadata,
                                access_key=access_key,
                                secret_key=secret_key,
                                queue_derive=queue_derive,
                                set_scanner=set_scanner)
            return request

        if debug:
            prepared_request = self.session.prepare_request(_build_request())
            body.close()
            return prepared_request
        else:
            try:
                while True:
                    error_msg = ('s3 is overloaded, sleeping for '
                                 f'{retries_sleep} seconds and retrying. '
                                 f'{retries} retries left.')
                    if retries > 0:
                        if self.session.s3_is_overloaded(access_key=access_key):
                            sleep(retries_sleep)
                            log.info(error_msg)
                            if verbose:
                                print(f' warning: {error_msg}', file=sys.stderr)
                            retries -= 1
                            continue
                    request = _build_request()
                    prepared_request = request.prepare()

                    # chunked transfer-encoding is NOT supported by IA-S3.
                    # It should NEVER be set. Requests adds it in certain
                    # scenarios (e.g. if content-length is 0). Stop it.
                    if prepared_request.headers.get('transfer-encoding') == 'chunked':
                        del prepared_request.headers['transfer-encoding']

                    response = self.session.send(prepared_request,
                                                 stream=True,
                                                 **request_kwargs)
                    if (response.status_code == 503) and (retries > 0):
                        if b'appears to be spam' in response.content:
                            log.info('detected as spam, upload failed')
                            break
                        log.info(error_msg)
                        if verbose:
                            print(f' warning: {error_msg}', file=sys.stderr)
                        sleep(retries_sleep)
                        retries -= 1
                        continue
                    else:
                        if response.status_code == 503:
                            log.info('maximum retries exceeded, upload failed.')
                        break
                response.raise_for_status()
                log.info(f'uploaded {key} to {url}')
                if delete and response.status_code == 200:
                    log.info(
                        f'{key} successfully uploaded to '
                        f'https://archive.org/download/{self.identifier}/{key} and verified, '
                        'deleting local copy')
                    body.close()
                    os.remove(filename)
                response.close()
                return response
            except HTTPError as exc:
                try:
                    msg = get_s3_xml_text(exc.response.content)  # type: ignore
                except ExpatError:  # probably HTTP 500 error and response is invalid XML
                    msg = ('IA S3 returned invalid XML '  # type: ignore
                           f'(HTTP status code {exc.response.status_code}). '
                           'This is a server side error which is either temporary, '
                           'or requires the intervention of IA admins.')

                error_msg = f' error uploading {key} to {self.identifier}, {msg}'
                log.error(error_msg)
                if verbose:
                    print(f' error uploading {key}: {msg}', file=sys.stderr)
                # Raise HTTPError with error message.
                raise type(exc)(error_msg, response=exc.response, request=exc.request)
            finally:
                body.close()

    def upload(self, files,
               metadata: Mapping | None = None,
               headers: dict | None = None,
               access_key: str | None = None,
               secret_key: str | None = None,
               queue_derive=None,  # TODO: True if None??
               verbose: bool = False,
               verify: bool = False,
               checksum: bool = False,
               delete: bool = False,
               retries: int | None = None,
               retries_sleep: int | None = None,
               debug: bool = False,
               validate_identifier: bool = False,
               request_kwargs: dict | None = None,
               set_scanner: bool = True) -> list[Request | Response]:
        r"""Upload files to an item. The item will be created if it
        does not exist.

        :type files: str, file, list, tuple, dict
        :param files: The filepaths or file-like objects to upload.

        :param \*\*kwargs: Optional arguments that :func:`Item.upload_file()` takes.

        :returns: A list of :class:`requests.Response` objects.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> md = {'mediatype': 'image', 'creator': 'Jake Johnson'}
            >>> item.upload('/path/to/image.jpg', metadata=md, queue_derive=False)
            [<Response [200]>]

        Uploading multiple files::

            >>> r = item.upload(['file1.txt', 'file2.txt'])
            >>> r = item.upload([fileobj, fileobj2])
            >>> r = item.upload(('file1.txt', 'file2.txt'))

        Uploading file objects:

            >>> import io
            >>> f = io.BytesIO(b'some initial binary data: \x00\x01')
            >>> r = item.upload({'remote-name.txt': f})
            >>> f = io.BytesIO(b'some more binary data: \x00\x01')
            >>> f.name = 'remote-name.txt'
            >>> r = item.upload(f)

            *Note: file objects must either have a name attribute, or be uploaded in a
            dict where the key is the remote-name*

        Setting the remote filename with a dict::

            >>> r = item.upload({'remote-name.txt': '/path/to/local/file.txt'})
        """
        queue_derive = True if queue_derive is None else queue_derive
        remote_dir_name = None
        total_files = 0
        if isinstance(files, dict):
            if files.get('name'):
                files = [files]
                total_files = 1
            else:
                files = list(files.items())
        if not isinstance(files, (list, tuple)):
            files = [files]
        if all(isinstance(f, dict) and f.get('name') for f in files):
            total_files = len(files)

        responses = []
        file_index = 0
        headers = headers or {}
        if (queue_derive or not headers.get('x-archive-size-hint')) and total_files == 0:
            total_files, total_size = recursive_file_count_and_size(files,
                                                                    item=self,
                                                                    checksum=checksum)
            if not headers.get('x-archive-size-hint'):
                headers['x-archive-size-hint'] = str(total_size)
        file_metadata = None
        for f in files:
            if isinstance(f, dict):
                if f.get('name'):
                    file_metadata = f.copy()
                    del file_metadata['name']
                    f = f['name']
            if ((isinstance(f, str) and is_dir(f))
                    or (isinstance(f, tuple) and is_dir(f[-1]))):
                if isinstance(f, tuple):
                    remote_dir_name = f[0].strip('/')
                    f = f[-1]
                for filepath, key in iter_directory(f):
                    file_index += 1
                    # Set derive header if queue_derive is True,
                    # and this is the last request being made.
                    if queue_derive is True and file_index >= total_files:
                        _queue_derive = True
                    else:
                        _queue_derive = False
                    if not f.endswith('/'):
                        if remote_dir_name:
                            key = f'{remote_dir_name}{f}/{key}'
                        else:
                            key = f'{f}/{key}'
                    elif remote_dir_name:
                        key = f'{remote_dir_name}/{key}'
                    key = norm_filepath(key)
                    resp = self.upload_file(filepath,
                                            key=key,
                                            metadata=metadata,
                                            file_metadata=file_metadata,
                                            headers=headers,
                                            access_key=access_key,
                                            secret_key=secret_key,
                                            queue_derive=_queue_derive,
                                            verbose=verbose,
                                            verify=verify,
                                            checksum=checksum,
                                            delete=delete,
                                            retries=retries,
                                            retries_sleep=retries_sleep,
                                            debug=debug,
                                            validate_identifier=validate_identifier,
                                            request_kwargs=request_kwargs,
                                            set_scanner=set_scanner)
                    responses.append(resp)
            else:
                file_index += 1
                # Set derive header if queue_derive is True,
                # and this is the last request being made.
                # if queue_derive is True and file_index >= len(files):
                if queue_derive is True and file_index >= total_files:
                    _queue_derive = True
                else:
                    _queue_derive = False

                if not isinstance(f, (list, tuple)):
                    key, body = (None, f)
                else:
                    key, body = f
                if key and not isinstance(key, str):
                    key = str(key)
                resp = self.upload_file(body,
                                        key=key,
                                        metadata=metadata,
                                        file_metadata=file_metadata,
                                        headers=headers,
                                        access_key=access_key,
                                        secret_key=secret_key,
                                        queue_derive=_queue_derive,
                                        verbose=verbose,
                                        verify=verify,
                                        checksum=checksum,
                                        delete=delete,
                                        retries=retries,
                                        retries_sleep=retries_sleep,
                                        debug=debug,
                                        validate_identifier=validate_identifier,
                                        request_kwargs=request_kwargs,
                                        set_scanner=set_scanner)
                responses.append(resp)
        return responses


class Collection(Item):
    """This class represents an archive.org collection."""

    def __init__(self, *args, **kwargs):
        self.searches = {}
        if isinstance(args[0], Item):
            orig = args[0]
            args = (orig.session, orig.identifier, orig.item_metadata)
        super().__init__(*args, **kwargs)
        if self.metadata.get('mediatype', 'collection') != 'collection':
            raise ValueError('mediatype is not "collection"!')

        deflt_srh = f'collection:{self.identifier}'
        self._make_search('contents',
                          self.metadata.get('search_collection', deflt_srh))
        self._make_search('subcollections',
                          f'{deflt_srh} AND mediatype:collection')

    def _do_search(self, name: str, query: str):
        rtn = self.searches.setdefault(
            name, self.session.search_items(query, fields=['identifier']))
        if not hasattr(self, f'{name}_count'):
            setattr(self, f'{name}_count', self.searches[name].num_found)
        return rtn.iter_as_items()

    def _make_search(self, name: str, query: str):
        setattr(self, name, lambda: self._do_search(name, query))
