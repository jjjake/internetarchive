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
internetarchive.item
~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2017 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals, print_function

import os
import sys
from fnmatch import fnmatch
from logging import getLogger
from time import sleep

try:
    from functools import total_ordering
except ImportError:
    from total_ordering import total_ordering
import json
from copy import deepcopy

from six import string_types
from six.moves import urllib
from requests import Response
from clint.textui import progress
from requests.exceptions import HTTPError

from internetarchive.utils import IdentifierListAsItems, get_md5, chunk_generator, \
    IterableToFileAdapter, iter_directory, recursive_file_count, norm_filepath
from internetarchive.files import File
from internetarchive.iarequest import MetadataRequest, S3Request
from internetarchive.utils import get_s3_xml_text, get_file_size

log = getLogger(__name__)


@total_ordering
class BaseItem(object):
    EXCLUDED_ITEM_METADATA_KEYS = (u'workable_servers', u'server')

    def __init__(self, identifier=None, item_metadata=None):
        # Default attributes.
        self.identifier = identifier
        self.item_metadata = {} if not item_metadata else item_metadata
        self.exists = None

        # Archive.org metadata attributes.
        self.metadata = {}
        self.files = []
        self.created = None
        self.d1 = None
        self.d2 = None
        self.dir = None
        self.files_count = None
        self.item_size = None
        self.reviews = []
        self.server = None
        self.uniq = None
        self.updated = None
        self.tasks = None
        self.is_dark = None

        # Load item.
        self.load()

    def __repr__(self):
        return ('{0.__class__.__name__}(identifier={0.identifier!r}{notloaded})'.format(
            self, notloaded=', item_metadata={}' if not self.exists else ''))

    def load(self, item_metadata=None):
        if item_metadata:
            self.item_metadata = item_metadata

        self.exists = True if self.item_metadata else False

        for key in self.item_metadata:
            setattr(self, key, self.item_metadata[key])

        if not self.identifier:
            self.identifier = self.metadata.get('identifier')

        mc = self.metadata.get('collection', [])
        self.collection = IdentifierListAsItems(mc, self.session)

    def __eq__(self, other):
        return self.item_metadata == other.item_metadata or \
            (self.item_metadata.keys() == other.item_metadata.keys() and
             all(self.item_metadata[x] == other.item_metadata[x]
                 for x in self.item_metadata
                 if x not in self.EXCLUDED_ITEM_METADATA_KEYS))

    def __le__(self, other):
        return self.identifier <= other.identifier

    def __hash__(self):
        without_excluded_keys = dict(
            (k, v) for (k, v) in self.item_metadata.items()
            if k not in self.EXCLUDED_ITEM_METADATA_KEYS)
        return hash(json.dumps(without_excluded_keys,
                               sort_keys=True, check_circular=False))


class Item(BaseItem):
    """This class represents an archive.org item. Generally this class
    should not be used directly, but rather via the
    ``internetarchive.get_item()`` function::

        >>> from internetarchive import get_item
        >>> item = get_item('stairs')
        >>> print(item.metadata)

    Or to modify the metadata for an item::

        >>> metadata = dict(title='The Stairs')
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

    def __init__(self, archive_session, identifier, item_metadata=None):
        """
        :type archive_session: :class:`ArchiveSession <ArchiveSession>`

        :type identifier: str
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

        :type item_metadata: dict
        :param item_metadata: (optional) The Archive.org item metadata used to initialize
                              this item.  If no item metadata is provided, it will be
                              retrieved from Archive.org using the provided identifier.
        """
        self.session = archive_session
        super(Item, self).__init__(identifier, item_metadata)

        self.urls = Item.URLs(self)

        if self.metadata.get('title'):
            # A copyable link to the item, in MediaWiki format
            self.wikilink = '* [{0.urls.details} {0.identifier}] ' \
                            '-- {0.metadata[title]}'.format(self)

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

        def _make_tab_URL(self, tab):
            """Make URLs for the separate tabs of Collections details page."""
            self._make_URL(tab, self.details + "&tab={tab}".format(tab=tab))

        DEFAULT_URL_FORMAT = '{0.session.protocol}//archive.org/{path}/{0.identifier}'

        def _make_URL(self, path, url_format=DEFAULT_URL_FORMAT):
            setattr(self, path, url_format.format(self._itm_obj, path=path))
            self._paths.append(path)

        def __str__(self):
            return "URLs ({1}) for {0.identifier}" \
                   .format(self._itm_obj, ', '.join(self._paths))

    def refresh(self, item_metadata=None, **kwargs):
        if not item_metadata:
            item_metadata = self.session.get_metadata(self.identifier, **kwargs)
        self.load(item_metadata)

    def get_file(self, file_name, file_metadata=None):
        """Get a :class:`File <File>` object for the named file.

        :rtype: :class:`internetarchive.File <File>`
        :returns: An :class:`internetarchive.File <File>` object.

        :type file_metadata: dict
        :param file_metadata: (optional) a dict of metadata for the
                              given fille.
        """
        return File(self, file_name, file_metadata)

    def get_files(self, files=None, formats=None, glob_pattern=None, on_the_fly=None):
        files = [] if not files else files
        formats = [] if not formats else formats
        on_the_fly = False if not on_the_fly else True

        if not isinstance(files, (list, tuple, set)):
            files = [files]
        if not isinstance(formats, (list, tuple, set)):
            formats = [formats]

        item_files = deepcopy(self.files)
        # Add support for on-the-fly files (e.g. EPUB).
        if on_the_fly:
            otf_files = [
                '{0}.epub'.format(self.identifier),
                '{0}.mobi'.format(self.identifier),
                '{0}_daisy.zip'.format(self.identifier),
                '{0}_archive_marc.xml'.format(self.identifier),
            ]
            for f in otf_files:
                item_files.append(dict(name=f, otf=True))

        if not any(k for k in [files, formats, glob_pattern]):
            for f in item_files:
                yield self.get_file(f.get('name'), file_metadata=f)

        for f in item_files:
            if f.get('name') in files:
                yield self.get_file(f.get('name'))
            elif f.get('format') in formats:
                yield self.get_file(f.get('name'))
            elif glob_pattern:
                if not isinstance(glob_pattern, list):
                    patterns = glob_pattern.split('|')
                else:
                    patterns = glob_pattern
                for p in patterns:
                    if fnmatch(f.get('name', ''), p):
                        yield self.get_file(f.get('name'))

    def download(self,
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
                 return_responses=None):
        """Download files from an item.

        :param files: (optional) Only download files matching given file names.

        :type formats: str
        :param formats: (optional) Only download files matching the given
                        Formats.

        :type glob_pattern: str
        :param glob_pattern: (optional) Only download files matching the given
                             glob pattern.

        :type dry_run: bool
        :param dry_run: (optional) Output download URLs to stdout, don't
                        download anything.

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

        :rtype: bool
        :returns: True if if all files have been downloaded successfully.
        """
        dry_run = False if dry_run is None else dry_run
        verbose = False if verbose is None else verbose
        silent = False if silent is None else silent
        ignore_existing = False if ignore_existing is None else ignore_existing
        ignore_errors = False if not ignore_errors else ignore_errors
        checksum = False if checksum is None else checksum
        no_directory = False if no_directory is None else no_directory
        return_responses = False if not return_responses else True

        if not dry_run:
            if item_index and verbose is True:
                print('{0} ({1}):'.format(self.identifier, item_index))
            elif item_index and silent is False:
                print('{0} ({1}): '.format(self.identifier, item_index), end='')
            elif item_index is None and verbose is True:
                print('{0}:'.format(self.identifier))
            elif item_index is None and silent is False:
                print(self.identifier, end=': ')
            sys.stdout.flush()

        if self.is_dark is True:
            msg = 'skipping {0}, item is dark'.format(self.identifier)
            log.warning(msg)
            if verbose:
                print(' ' + msg)
            elif silent is False:
                print(msg)
            return
        elif self.metadata == {}:
            msg = 'skipping {0}, item does not exist.'.format(self.identifier)
            log.warning(msg)
            if verbose:
                print(' ' + msg)
            elif silent is False:
                print(msg)
            return

        if files:
            files = self.get_files(files, on_the_fly=on_the_fly)
        else:
            files = self.get_files(on_the_fly=on_the_fly)
        if formats:
            files = self.get_files(formats=formats, on_the_fly=on_the_fly)
        if glob_pattern:
            files = self.get_files(glob_pattern=glob_pattern, on_the_fly=on_the_fly)

        if not files:
            msg = 'skipping {0}, no matching files found.'.format(self.identifier)
            log.info(msg)
            if verbose:
                print(' ' + msg)
            elif silent is False:
                print(msg, end='')

        errors = list()
        responses = list()
        for f in files:
            if no_directory:
                path = f.name
            else:
                path = os.path.join(self.identifier, f.name)
            if dry_run:
                print(f.url)
                continue
            r = f.download(path, verbose, silent, ignore_existing, checksum, destdir,
                           retries, ignore_errors, None, return_responses)
            if return_responses:
                responses.append(r)
            if r is False:
                errors.append(f.name)
        if silent is False and verbose is False and dry_run is False:
            if errors:
                print(' - errors')
            else:
                print(' - success')
        if return_responses:
            return responses
        else:
            return errors

    def modify_metadata(self, metadata,
                        target=None,
                        append=None,
                        priority=None,
                        access_key=None,
                        secret_key=None,
                        debug=None,
                        request_kwargs=None):
        """Modify the metadata of an existing item on Archive.org.

        Note: The Metadata Write API does not yet comply with the
        latest Json-Patch standard. It currently complies with `version 02
        <https://tools.ietf.org/html/draft-ietf-appsawg-json-patch-02>`__.

        :type metadata: dict
        :param metadata: Metadata used to update the item.

        :type target: str
        :param target: (optional) Set the metadata target to update.

        :type priority: int
        :param priority: (optional) Set task priority.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('mapi_test_item1')
            >>> md = dict(new_key='new_value', foo=['bar', 'bar2'])
            >>> item.modify_metadata(md)

        :rtype: dict
        :returns: A dictionary containing the status_code and response
                  returned from the Metadata API.
        """
        target = 'metadata' if target is None else target
        append = False if append is None else append
        access_key = self.session.access_key if not access_key else access_key
        secret_key = self.session.secret_key if not secret_key else secret_key
        debug = False if debug is None else debug
        request_kwargs = {} if not request_kwargs else request_kwargs

        url = '{protocol}//archive.org/metadata/{identifier}'.format(
            protocol=self.session.protocol,
            identifier=self.identifier)
        request = MetadataRequest(
            method='POST',
            url=url,
            metadata=metadata,
            headers=self.session.headers,
            source_metadata=self.item_metadata.get(target.split('/')[0], {}),
            target=target,
            priority=priority,
            access_key=access_key,
            secret_key=secret_key,
            append=append)
        # Must use Session.prepare_request to make sure session settings
        # are used on request!
        prepared_request = request.prepare()
        if debug:
            return prepared_request
        resp = self.session.send(prepared_request, **request_kwargs)
        # Re-initialize the Item object with the updated metadata.
        self.refresh()
        return resp

    def upload_file(self, body,
                    key=None,
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
                    request_kwargs=None):
        """Upload a single file to an item. The item will be created
        if it does not exist.

        :type body: Filepath or file-like object.
        :param body: File or data to be uploaded.

        :type key: str
        :param key: (optional) Remote filename.

        :type metadata: dict
        :param metadata: (optional) Metadata used to create a new item.

        :type headers: dict
        :param headers: (optional) Add additional IA-S3 headers to request.

        :type queue_derive: bool
        :param queue_derive: (optional) Set to False to prevent an item from
                             being derived after upload.

        :type verify: bool
        :param verify: (optional) Verify local MD5 checksum matches the MD5
                       checksum of the file received by IAS3.

        :type checksum: bool
        :param checksum: (optional) Skip based on checksum.

        :type delete: bool
        :param delete: (optional) Delete local file after the upload has been
                       successfully verified.

        :type retries: int
        :param retries: (optional) Number of times to retry the given request
                        if S3 returns a 503 SlowDown error.

        :type retries_sleep: int
        :param retries_sleep: (optional) Amount of time to sleep between
                              ``retries``.

        :type verbose: bool
        :param verbose: (optional) Print progress to stdout.

        :type debug: bool
        :param debug: (optional) Set to True to print headers to stdout, and
                      exit without sending the upload request.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> item.upload_file('/path/to/image.jpg',
            ...                  key='photos/image1.jpg')
            True
        """
        # Set defaults.
        headers = {} if headers is None else headers
        metadata = {} if metadata is None else metadata
        access_key = self.session.access_key if access_key is None else access_key
        secret_key = self.session.secret_key if secret_key is None else secret_key
        queue_derive = True if queue_derive is None else queue_derive
        verbose = False if verbose is None else verbose
        verify = True if verify is None else verify
        delete = False if delete is None else delete
        # Set checksum after delete.
        checksum = True if delete else checksum
        retries = 0 if retries is None else retries
        retries_sleep = 30 if retries_sleep is None else retries_sleep
        debug = False if debug is None else debug
        request_kwargs = {} if request_kwargs is None else request_kwargs
        if 'timeout' not in request_kwargs:
            request_kwargs['timeout'] = 120
        md5_sum = None

        if not hasattr(body, 'read'):
            filename = body
            body = open(body, 'rb')
        else:
            if key:
                filename = key
            else:
                filename = body.name

        size = get_file_size(body)

        # Support for uploading empty files.
        if size == 0:
            headers['Content-Length'] = '0'

        if not headers.get('x-archive-size-hint'):
            headers['x-archive-size-hint'] = str(size)

        # Build IA-S3 URL.
        key = norm_filepath(filename).split('/')[-1] if key is None else key
        base_url = '{0.session.protocol}//s3.us.archive.org/{0.identifier}'.format(self)
        url = '{0}/{1}'.format(
            base_url, urllib.parse.quote(norm_filepath(key).lstrip('/').encode('utf-8')))

        # Skip based on checksum.
        if checksum:
            md5_sum = get_md5(body)
            ia_file = self.get_file(key)
            if (not self.tasks) and (ia_file) and (ia_file.md5 == md5_sum):
                log.info('{f} already exists: {u}'.format(f=key, u=url))
                if verbose:
                    print(' {f} already exists, skipping.'.format(f=key))
                if delete:
                    log.info(
                        '{f} successfully uploaded to '
                        'https://archive.org/download/{i}/{f} '
                        'and verified, deleting '
                        'local copy'.format(i=self.identifier,
                                            f=key))
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
            headers['Content-MD5'] = md5_sum

        def _build_request():
            body.seek(0, os.SEEK_SET)
            if verbose:
                try:
                    # hack to raise exception so we get some output for
                    # empty files.
                    if size == 0:
                        raise Exception

                    chunk_size = 1048576
                    expected_size = size / chunk_size + 1
                    chunks = chunk_generator(body, chunk_size)
                    progress_generator = progress.bar(
                        chunks,
                        expected_size=expected_size,
                        label=' uploading {f}: '.format(f=key))
                    data = IterableToFileAdapter(progress_generator, size)
                except:
                    print(' uploading {f}'.format(f=key))
                    data = body
            else:
                data = body

            headers.update(self.session.headers)
            request = S3Request(method='PUT',
                                url=url,
                                headers=headers,
                                data=data,
                                metadata=metadata,
                                access_key=access_key,
                                secret_key=secret_key,
                                queue_derive=queue_derive)
            return request

        if debug:
            prepared_request = self.session.prepare_request(_build_request())
            body.close()
            return prepared_request
        else:
            try:
                error_msg = ('s3 is overloaded, sleeping for '
                             '{0} seconds and retrying. '
                             '{1} retries left.'.format(retries_sleep, retries))
                while True:
                    if retries > 0:
                        if self.session.s3_is_overloaded(access_key):
                            sleep(retries_sleep)
                            log.info(error_msg)
                            if verbose:
                                print(' warning: {0}'.format(error_msg), file=sys.stderr)
                            retries -= 1
                            continue
                    request = _build_request()
                    prepared_request = request.prepare()

                    # chunked transer-encoding is NOT supported by IA-S3.
                    # It should NEVER be set. Requests adds it in certain
                    # scenarios (e.g. if content-length is 0). Stop it.
                    if prepared_request.headers.get('transfer-encoding') == 'chunked':
                        del prepared_request.headers['transfer-encoding']

                    response = self.session.send(prepared_request,
                                                 stream=True,
                                                 **request_kwargs)
                    if (response.status_code == 503) and (retries > 0):
                        log.info(error_msg)
                        if verbose:
                            print(' warning: {0}'.format(error_msg), file=sys.stderr)
                        sleep(retries_sleep)
                        retries -= 1
                        continue
                    else:
                        if response.status_code == 503:
                            log.info('maximum retries exceeded, upload failed.')
                        break
                response.raise_for_status()
                log.info(u'uploaded {f} to {u}'.format(f=key, u=url))
                if delete and response.status_code == 200:
                    log.info(
                        '{f} successfully uploaded to '
                        'https://archive.org/download/{i}/{f} and verified, deleting '
                        'local copy'.format(i=self.identifier, f=key))
                    body.close()
                    os.remove(filename)
                body.close()
                return response
            except HTTPError as exc:
                body.close()
                msg = get_s3_xml_text(exc.response.content)
                error_msg = (' error uploading {0} to {1}, '
                             '{2}'.format(key, self.identifier, msg))
                log.error(error_msg)
                if verbose:
                    print(' error uploading {0}: {1}'.format(key, msg), file=sys.stderr)
                # Raise HTTPError with error message.
                raise type(exc)(error_msg, response=exc.response, request=exc.request)

    def upload(self, files,
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
               request_kwargs=None):
        """Upload files to an item. The item will be created if it
        does not exist.

        :type files: list
        :param files: The filepaths or file-like objects to upload.

        :type kwargs: dict
        :param kwargs: The keyword arguments from the call to
                       upload_file().

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> md = dict(mediatype='image', creator='Jake Johnson')
            >>> item.upload('/path/to/image.jpg', metadata=md, queue_derive=False)
            True

        :rtype: list
        :returns: A list of requests.Response objects.
        """
        queue_derive = True if queue_derive is None else queue_derive
        remote_dir_name = None
        if isinstance(files, dict):
            files = list(files.items())
        if not isinstance(files, (list, tuple)):
            files = [files]

        responses = []
        file_index = 0
        if checksum:
            total_files = recursive_file_count(files, item=self, checksum=True)
        else:
            total_files = recursive_file_count(files, item=self, checksum=False)
        for f in files:
            if (isinstance(f, string_types) and os.path.isdir(f)) \
                    or (isinstance(f, tuple) and os.path.isdir(f[-1])):
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
                            key = '{0}{1}/{2}'.format(remote_dir_name, f, key)
                        else:
                            key = '{0}/{1}'.format(f, key)
                    elif remote_dir_name:
                        key = '{0}/{1}'.format(remote_dir_name, key)
                    key = norm_filepath(key)
                    resp = self.upload_file(filepath,
                                            key=key,
                                            metadata=metadata,
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
                                            request_kwargs=request_kwargs)
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
                if key and not isinstance(key, string_types):
                    key = str(key)
                resp = self.upload_file(body,
                                        key=key,
                                        metadata=metadata,
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
                                        request_kwargs=request_kwargs)
                responses.append(resp)
        return responses


class Collection(Item):
    """This class represents an archive.org collection."""

    def __init__(self, *args, **kwargs):
        self.searches = {}
        if isinstance(args[0], Item):
            orig = args[0]
            args = (orig.session, orig.identifier, orig.item_metadata)
        super(Collection, self).__init__(*args, **kwargs)
        if self.metadata.get(u'mediatype', u'collection') != 'collection':
            raise ValueError('mediatype is not "collection"!')

        deflt_srh = "collection:{0.identifier}".format(self)
        self._make_search('contents',
                          self.metadata.get(u'search_collection', deflt_srh))
        self._make_search('subcollections',
                          deflt_srh + " AND mediatype:collection")

    def _do_search(self, name, query):
        rtn = self.searches.setdefault(
            name, self.session.search_items(query, fields=[u'identifier']))
        if not hasattr(self, name + "_count"):
            setattr(self, name + "_count", self.searches[name].num_found)
        return rtn.iter_as_items()

    def _make_search(self, name, query):
        setattr(self, name, lambda: self._do_search(name, query))
