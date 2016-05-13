# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals, print_function

from logging import getLogger
from fnmatch import fnmatch
import os
from time import sleep
import sys
try:
    from functools import total_ordering
except ImportError:
    from total_ordering import total_ordering
import json

from six import string_types
from six.moves import urllib
from requests import Response
from clint.textui import progress
from requests.exceptions import HTTPError

from internetarchive.utils import IdentifierListAsItems, get_md5, chunk_generator, \
    IterableToFileAdapter
from internetarchive.files import File
from internetarchive.iarequest import MetadataRequest, S3Request
from internetarchive.utils import get_s3_xml_text, get_file_size
from internetarchive import __version__


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
        return ('{0.__class__.__name__}(identifier={identifier!r}, '
                'exists={exists!r})'.format(self, **self.__dict__))

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
    """This class represents an archive.org item. You can use this
    class to access item metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> print(item.metadata)

    Or to modify the metadata for an item::

        >>> metadata = dict(title='The Stairs')
        >>> item.modify(metadata)
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

    def refresh(self, item_metadata=None, **kwargs):
        if not item_metadata:
            item_metadata = self.session.get_metadata(self.identifier, **kwargs)
        self.load(item_metadata)

    def get_file(self, file_name):
        """Get a :class:`File <File>` object for the named file.

        :rtype: :class:`internetarchive.File <File>`
        :returns: An :class:`internetarchive.File <File>` object.
        """
        return File(self, file_name)

    def get_files(self, files=None, formats=None, glob_pattern=None):
        files = [] if not files else files
        formats = [] if not formats else formats

        if not isinstance(files, (list, tuple, set)):
            files = [files]
        if not isinstance(formats, (list, tuple, set)):
            formats = [formats]

        if not any(k for k in [files, formats, glob_pattern]):
            for f in self.files:
                yield self.get_file(f.get('name'))

        for f in self.files:
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
                 ignore_errors=None):
        """Download files from an item.

        :param files: (optional) Only download files matching given file names.

        :type formats: str
        :param formats: (optional) Only download files matching the given Formats.

        :type glob_pattern: str
        :param glob_pattern: (optional) Only download files matching the given glob
                             pattern.

        :type clobber: bool
        :param clobber: (optional) Overwrite local files if they already exist.

        :type no_clobber: bool
        :param no_clobber: (optional) Do not overwrite local files if they already exist,
                           or raise an IOError exception.

        :type checksum: bool
        :param checksum: (optional) Skip downloading file based on checksum.

        :type no_directory: bool
        :param no_directory: (optional) Download files to current working directory rather
                             than creating an item directory.

        :rtype: bool
        :returns: True if if files have been downloaded successfully.
        """
        dry_run = False if dry_run is None else dry_run
        verbose = False if verbose is None else verbose
        silent = False if silent is None else silent
        ignore_existing = False if ignore_existing is None else ignore_existing
        ignore_errors = False if not ignore_errors else ignore_errors
        checksum = False if checksum is None else checksum
        no_directory = False if no_directory is None else no_directory

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
            files = self.get_files(files)
        else:
            files = self.get_files()
        if formats:
            files = self.get_files(formats=formats)
        if glob_pattern:
            files = self.get_files(glob_pattern=glob_pattern)

        if not files:
            msg = 'skipping {0}, no matching files found.'.format(self.identifier)
            log.info(msg)
            if verbose:
                print(' ' + msg)
            elif silent is False:
                print(msg, end='')

        errors = list()
        for f in files:
            if no_directory:
                path = f.name
            else:
                path = os.path.join(self.identifier, f.name)
            if dry_run:
                print(f.url)
                continue
            r = f.download(path, verbose, silent, ignore_existing, checksum, destdir,
                           retries, ignore_errors)
            if r is False:
                errors.append(f.name)
        if silent is False and verbose is False and dry_run is False:
            if errors:
                print(' - errors')
            else:
                print(' - success')
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
            url=url,
            metadata=metadata,
            source_metadata=self.item_metadata.get(target.split('/')[0], {}),
            target=target,
            priority=priority,
            access_key=access_key,
            secret_key=secret_key,
            append=append)
        if debug:
            return request
        prepared_request = request.prepare()
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
        checksum = True if delete or checksum is None else checksum
        retries = 0 if retries is None else retries
        retries_sleep = 30 if retries_sleep is None else retries_sleep
        debug = False if debug is None else debug
        request_kwargs = {} if request_kwargs is None else request_kwargs
        md5_sum = None

        if not hasattr(body, 'read'):
            body = open(body, 'rb')

        size = get_file_size(body)

        if not headers.get('x-archive-size-hint'):
            headers['x-archive-size-hint'] = size

        # Build IA-S3 URL.
        key = body.name.split('/')[-1] if key is None else key
        base_url = '{0.session.protocol}//s3.us.archive.org/{0.identifier}'.format(self)
        url = '{0}/{1}'.format(
            base_url, urllib.parse.quote(key.lstrip('/').encode('utf-8')))

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
                    os.remove(body.name)
                # Return an empty response object if checksums match.
                # TODO: Is there a better way to handle this?
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
            return _build_request()
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
                log.info('uploaded {f} to {u}'.format(f=key, u=url))
                if delete and response.status_code == 200:
                    log.info(
                        '{f} successfully uploaded to '
                        'https://archive.org/download/{i}/{f} and verified, deleting '
                        'local copy'.format(i=self.identifier,
                                            f=key))
                    os.remove(body.name)
                return response
            except HTTPError as exc:
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

        :rtype: bool
        :returns: True if the request was successful and all files were
                  uploaded, False otherwise.
        """
        def iter_directory(directory):
            for path, dir, files in os.walk(directory):
                for f in files:
                    filepath = os.path.join(path, f)
                    key = os.path.relpath(filepath, directory)
                    yield (filepath, key)

        queue_derive = True if queue_derive is None else queue_derive
        if isinstance(files, dict):
            files = list(files.items())
        if not isinstance(files, (list, tuple)):
            files = [files]

        responses = []
        file_index = 0
        for f in files:
            file_index += 1
            if isinstance(f, string_types) and os.path.isdir(f):
                fdir_index = 0
                for filepath, key in iter_directory(f):
                    # Set derive header if queue_derive is True,
                    # and this is the last request being made.
                    fdir_index += 1
                    if queue_derive is True and file_index >= len(files) \
                            and fdir_index >= len(os.listdir(f)):
                        queue_derive = True
                    else:
                        queue_derive = False
                    if not f.endswith('/'):
                        key = '{0}/{1}'.format(f, key)
                    resp = self.upload_file(filepath,
                                            key=key,
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
                    responses.append(resp)
            else:
                # Set derive header if queue_derive is True,
                # and this is the last request being made.
                if queue_derive is True and file_index >= len(files):
                    queue_derive = True
                else:
                    queue_derive = False

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
                                        queue_derive=queue_derive,
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
