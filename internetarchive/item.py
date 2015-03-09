import os
import sys
from fnmatch import fnmatch
import logging
import time

import requests.sessions
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from requests import Response
from clint.textui import progress
import six
import six.moves.urllib as urllib

from . import __version__, session, iarequest, utils


log = logging.getLogger(__name__)


# Item class
# ________________________________________________________________________________________
class Item(object):
    """This class represents an archive.org item. You can use this
    class to access item metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> print(item.metadata)

    Or to modify the metadata for an item::

        >>> metadata = dict(title='The Stairs')
        >>> item.modify(metadata)
        >>> print(item.metadata['title'])
        u'The Stairs'

    This class also uses IA's S3-like interface to upload files to an
    item. You need to supply your IAS3 credentials in environment
    variables in order to upload::

        >>> item.upload('myfile.tar', access_key='Y6oUrAcCEs4sK8ey',
        ...                           secret_key='youRSECRETKEYzZzZ')
        True

    You can retrieve S3 keys here: `https://archive.org/account/s3.php
    <https://archive.org/account/s3.php>`__

    """
    # init()
    # ____________________________________________________________________________________
    def __init__(self, identifier, metadata_timeout=None, config=None, max_retries=1,
                 archive_session=None):
        """
        :type identifier: str
        :param identifier: The globally unique Archive.org identifier
                           for a given item.

        :type metadata_timeout: int
        :param metadata_timeout: (optional) Set a timeout for retrieving
                                 an item's metadata.

        :type config: dict
        :param secure: (optional) Configuration options for session.

        :type max_retries: int
        :param max_retries: (optional) Maximum number of times to request
                            a website if the connection drops. (default: 1)

        :type archive_session: :class:`ArchiveSession <ArchiveSession>`
        :param archive_session: An :class:`ArchiveSession <ArchiveSession>`
                                object can be provided via the `archive_session`
                                parameter.

        """
        self.session = archive_session if archive_session else session.get_session(config)
        self.protocol = 'https:' if self.session.secure else 'http:'
        self.http_session = requests.sessions.Session()
        max_retries_adapter = HTTPAdapter(max_retries=max_retries)
        self.http_session.mount('{0}//'.format(self.protocol), max_retries_adapter)
        self.http_session.cookies = self.session.cookies
        self.identifier = identifier

        # Default empty attributes.
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

        self._json = self.get_metadata(metadata_timeout)
        self.exists = False if self._json == {} else True

    # __repr__()
    # ____________________________________________________________________________________
    def __repr__(self):
        return ('Item(identifier={identifier!r}, '
                'exists={exists!r})'.format(**self.__dict__))

    # get_metadata()
    # ____________________________________________________________________________________
    def get_metadata(self, metadata_timeout=None):
        """Get an item's metadata from the `Metadata API
        <http://blog.archive.org/2013/07/04/metadata-api/>`__

        :type identifier: str
        :param identifier: Globally unique Archive.org identifier.

        :rtype: dict
        :returns: Metadat API response.

        """
        url = '{protocol}//archive.org/metadata/{identifier}'.format(**self.__dict__)
        try:
            resp = self.http_session.get(url, timeout=metadata_timeout)
            resp.raise_for_status()
        except HTTPError as e:
            error_msg = 'Error retrieving metadata from {0}, {1}'.format(resp.url, e)
            log.error(error_msg)
            raise HTTPError(error_msg)
        metadata = resp.json()
        for key in metadata:
                setattr(self, key, metadata[key])
        return metadata

    # iter_files()
    # ____________________________________________________________________________________
    def iter_files(self):
        """Generator for iterating over files in an item.

        :rtype: generator
        :returns: A generator that yields :class:`internetarchive.File
                  <File>` objects.

        """
        for file_dict in self.files:
            file = File(self, file_dict.get('name'))
            yield file

    # file()
    # ____________________________________________________________________________________
    def get_file(self, file_name):
        """Get a :class:`File <File>` object for the named file.

        :rtype: :class:`internetarchive.File <File>`
        :returns: An :class:`internetarchive.File <File>` object.

        """
        for f in self.iter_files():
            if f.name == file_name:
                return f

    # get_files()
    # ____________________________________________________________________________________
    def get_files(self, files=None, source=None, formats=None, glob_pattern=None):
        files = [] if not files else files
        source = [] if not source else source

        if not isinstance(files, (list, tuple, set)):
            files = [files]
        if not isinstance(source, (list, tuple, set)):
            source = [source]
        if not isinstance(formats, (list, tuple, set)):
            formats = [formats]

        file_objects = []
        for f in self.iter_files():
            if f.name in files:
                file_objects.append(f)
            elif f.source in source:
                file_objects.append(f)
            elif f.format in formats:
                file_objects.append(f)
            elif glob_pattern:
                # Support for | operator.
                patterns = glob_pattern.split('|')
                if not isinstance(patterns, list):
                    patterns = [patterns]
                for p in patterns:
                    if fnmatch(f.name, p):
                        file_objects.append(f)
        return file_objects

    # download()
    # ____________________________________________________________________________________
    def download(self, concurrent=None, source=None, formats=None, glob_pattern=None,
                 dry_run=None, verbose=None, ignore_existing=None, checksum=None,
                 destdir=None, no_directory=None):
        """Download the entire item into the current working directory.

        :type concurrent: bool
        :param concurrent: Download files concurrently if ``True``.

        :type source: str
        :param source: Only download files matching given source.

        :type formats: str
        :param formats: Only download files matching the given Formats.

        :type glob_pattern: str
        :param glob_pattern: Only download files matching the given glob
                             pattern

        :type ignore_existing: bool
        :param ignore_existing: Overwrite local files if they already
                                exist.

        :type checksum: bool
        :param checksum: Skip downloading file based on checksum.

        :type no_directory: bool
        :param no_directory: Download files to current working
                             directory rather than creating an item
                             directory.

        :rtype: bool
        :returns: True if if files have been downloaded successfully.

        """
        concurrent = False if concurrent is None else concurrent
        dry_run = False if dry_run is None else dry_run
        verbose = False if verbose is None else verbose
        ignore_existing = False if ignore_existing is None else ignore_existing
        checksum = False if checksum is None else checksum
        no_directory = False if no_directory is None else no_directory

        if verbose:
            sys.stdout.write('{0}:\n'.format(self.identifier))
            if self._json.get('is_dark') is True:
                sys.stdout.write(' skipping: item is dark.\n')
                log.warning('Not downloading item {0}, '
                            'item is dark'.format(self.identifier))
            elif self.metadata == {}:
                sys.stdout.write(' skipping: item does not exist.\n')
                log.warning('Not downloading item {0}, '
                            'item does not exist.'.format(self.identifier))

        if concurrent:
            try:
                from gevent import monkey
                monkey.patch_socket()
                from gevent.pool import Pool
                pool = Pool()
            except ImportError:
                raise ImportError(
                    """No module named gevent

                    Downloading files concurrently requires the gevent neworking library.
                    gevent and all of it's dependencies can be installed with pip:

                    \tpip install cython git+git://github.com/surfly/gevent.git@1.0rc2#egg=gevent

                    """)

        files = self.iter_files()
        if source:
            files = self.get_files(source=source)
        if formats:
            files = self.get_files(formats=formats)
        if glob_pattern:
            files = self.get_files(glob_pattern=glob_pattern)

        if not files and verbose:
            sys.stdout.write(' no matching files found, nothing downloaded.\n')
        for f in files:
            fname = f.name.encode('utf-8')
            if no_directory:
                path = fname
            else:
                path = os.path.join(self.identifier, fname)
            if dry_run:
                sys.stdout.write(f.url + '\n')
                continue
            if concurrent:
                pool.spawn(f.download, path, verbose, ignore_existing, checksum, destdir)
            else:
                f.download(path, verbose, ignore_existing, checksum, destdir)
        if concurrent:
            pool.join()
        return True

    # modify_metadata()
    # ____________________________________________________________________________________
    def modify_metadata(self, metadata, target=None, append=False, priority=None,
                        access_key=None, secret_key=None, debug=False):
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
        access_key = self.session.access_key if not access_key else access_key
        secret_key = self.session.secret_key if not secret_key else secret_key
        target = 'metadata' if target is None else target

        url = '{protocol}//archive.org/metadata/{identifier}'.format(**self.__dict__)
        request = iarequest.MetadataRequest(
            url=url,
            metadata=metadata,
            source_metadata=self._json.get(target.split('/')[0], {}),
            target=target,
            priority=priority,
            access_key=access_key,
            secret_key=secret_key,
            append=append,
        )
        if debug:
            return request
        prepared_request = request.prepare()
        resp = self.http_session.send(prepared_request)
        self._json = self.get_metadata()
        return resp

    # s3_is_overloaded()
    # ____________________________________________________________________________________
    def s3_is_overloaded(self, access_key=None):
        u = 'http://s3.us.archive.org'
        p = dict(
            check_limit=1,
            accesskey=access_key,
            bucket=self.identifier,
        )
        r = self.http_session.get(u, params=p)
        j = r.json()
        if j.get('over_limit') == 0:
            return False
        else:
            return True

    # upload_file()
    # ____________________________________________________________________________________
    def upload_file(self, body, key=None, metadata=None, headers=None,
                    access_key=None, secret_key=None, queue_derive=True,
                    ignore_preexisting_bucket=False, verbose=False, verify=True,
                    checksum=False, delete=False, retries=None, retries_sleep=None,
                    debug=False, **kwargs):
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

        :type ignore_preexisting_bucket: bool
        :param ignore_preexisting_bucket: (optional) Destroy and respecify the
                                          metadata for an item

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
        # Defaults for empty params.
        headers = {} if headers is None else headers
        metadata = {} if metadata is None else metadata
        access_key = self.session.access_key if access_key is None else access_key
        secret_key = self.session.secret_key if secret_key is None else secret_key
        retries = 0 if retries is None else retries
        retries_sleep = 30 if retries_sleep is None else retries_sleep

        if not hasattr(body, 'read'):
            body = open(body, 'rb')

        if not metadata.get('scanner'):
            scanner = 'Internet Archive Python library {0}'.format(__version__)
            metadata['scanner'] = scanner

        try:
            body.seek(0, os.SEEK_END)
            size = body.tell()
            body.seek(0, os.SEEK_SET)
        except IOError:
            size = None

        if not headers.get('x-archive-size-hint'):
            headers['x-archive-size-hint'] = size

        key = body.name.split('/')[-1] if key is None else key
        base_url = '{protocol}//s3.us.archive.org/{identifier}'.format(**self.__dict__)
        url = '{base_url}/{key}'.format(base_url=base_url, key=urllib.parse.quote(key))

        # Skip based on checksum.
        md5_sum = utils.get_md5(body)
        ia_file = self.get_file(key)
        if (checksum) and (not self.tasks) and (ia_file) and (ia_file.md5 == md5_sum):
            log.info('{f} already exists: {u}'.format(f=key, u=url))
            if verbose:
                sys.stdout.write(' {f} already exists, skipping.\n'.format(f=key))
            if delete:
                log.info(
                    '{f} successfully uploaded to https://archive.org/download/{i}/{f} '
                    'and verified, deleting '
                    'local copy'.format(i=self.identifier, f=key)
                )
                os.remove(body.name)
            # Return an empty response object if checksums match.
            # TODO: Is there a better way to handle this?
            return Response()

        # require the Content-MD5 header when delete is True.
        if verify or delete:
            headers['Content-MD5'] = md5_sum

        # Delete retries and sleep_retries from kwargs.
        if 'retries' in kwargs:
            del kwargs['retries']
        if 'retries_sleep' in kwargs:
            del kwargs['retries_sleep']

        def _build_request():
            body.seek(0, os.SEEK_SET)
            if verbose:
                try:
                    chunk_size = 1048576
                    expected_size = size/chunk_size + 1
                    chunks = utils.chunk_generator(body, chunk_size)
                    progress_generator = progress.bar(chunks, expected_size=expected_size,
                                                      label=' uploading {f}: '.format(f=key))
                    data = utils.IterableToFileAdapter(progress_generator, size)
                except:
                    sys.stdout.write(' uploading {f}: '.format(f=key))
                    data = body
            else:
                data = body

            request = iarequest.S3Request(
                method='PUT',
                url=url,
                headers=headers,
                data=data,
                metadata=metadata,
                access_key=access_key,
                secret_key=secret_key,
                queue_derive=queue_derive,
                **kwargs
            )
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
                        if self.s3_is_overloaded(access_key):
                            time.sleep(retries_sleep)
                            log.info(error_msg)
                            if verbose:
                                sys.stderr.write(' warning: {0}\n'.format(error_msg))
                            retries -= 1
                            continue
                    request = _build_request()
                    prepared_request = request.prepare()
                    response = self.http_session.send(prepared_request, stream=True)
                    if (response.status_code == 503) and (retries > 0):
                        log.info(error_msg)
                        if verbose:
                            sys.stderr.write(' warning: {0}\n'.format(error_msg))
                        time.sleep(retries_sleep)
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
                        'local copy'.format(i=self.identifier, f=key)
                    )
                    os.remove(body.name)
                return response
            except HTTPError as exc:
                error_msg = (' error uploading {0} to {1}, '
                             '{2}'.format(key, self.identifier, exc))
                log.error(error_msg)
                if verbose:
                    sys.stderr.write(error_msg + '\n')
                # Raise HTTPError with error message.
                raise type(exc)(error_msg)

    # upload()
    # ____________________________________________________________________________________
    def upload(self, files, **kwargs):
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

        if isinstance(files, dict):
            files = files.items()
        if not isinstance(files, (list, tuple)):
            files = [files]

        queue_derive = kwargs.get('queue_derive', True)

        responses = []
        file_index = 0
        for f in files:
            file_index += 1
            if isinstance(f, six.string_types) and os.path.isdir(f):
                fdir_index = 0
                for filepath, key in iter_directory(f):
                    # Set derive header if queue_derive is True,
                    # and this is the last request being made.
                    fdir_index += 1
                    if queue_derive is True and file_index >= len(files) \
                        and fdir_index >= len(os.listdir(f)):
                            kwargs['queue_derive'] = True
                    else:
                        kwargs['queue_derive'] = False

                    if not f.endswith('/'):
                        key = '{0}/{1}'.format(f, key)
                    resp = self.upload_file(filepath, key=key, **kwargs)
                    responses.append(resp)
            else:
                # Set derive header if queue_derive is True,
                # and this is the last request being made.
                if queue_derive is True and file_index >= len(files):
                    kwargs['queue_derive'] = True
                else:
                    kwargs['queue_derive'] = False

                if not isinstance(f, (list, tuple)):
                    key, body = (None, f)
                else:
                    key, body = f
                if key and not isinstance(key, six.string_types):
                    raise ValueError('Key must be a string.')
                resp = self.upload_file(body, key=key, **kwargs)
                responses.append(resp)
        return responses


# File class
# ________________________________________________________________________________________
class File(object):
    """This class represents a file in an archive.org item. You
    can use this class to access the file metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> file = internetarchive.File(item, 'stairs.avi')
        >>> print(f.format, f.size)
        (u'Cinepack', u'3786730')

    Or to download a file::

        >>> file.download()
        >>> file.download('fabulous_movie_of_stairs.avi')

    This class also uses IA's S3-like interface to delete a file
    from an item. You need to supply your IAS3 credentials in
    environment variables in order to delete::

        >>> file.delete(access_key='Y6oUrAcCEs4sK8ey',
        ...             secret_key='youRSECRETKEYzZzZ')

    You can retrieve S3 keys here: `https://archive.org/account/s3.php
    <https://archive.org/account/s3.php>`__

    """
    # init()
    # ____________________________________________________________________________________
    def __init__(self, item, name):
        """
        :type item: Item
        :param item: The item that the file is part of.

        :type name: str
        :param name: The filename of the file.

        """
        _file = {}
        for f in item.files:
            if f.get('name') == name:
                _file = f
                break

        self._item = item
        self.identifier = item.identifier
        self.name = None
        self.size = None
        self.source = None
        self.format = None
        self.md5 = None
        for key in _file:
            setattr(self, key, _file[key])
        base_url = '{protocol}//archive.org/download/{identifier}'.format(**item.__dict__)
        self.url = '{base_url}/{name}'.format(base_url=base_url,
                                              name=urllib.parse.quote(name.encode('utf-8')))

    # __repr__()
    # ____________________________________________________________________________________
    def __repr__(self):
        return ('File(identifier={identifier!r}, '
                'filename={name!r}, '
                'size={size!r}, '
                'source={source!r}, '
                'format={format!r})'.format(**self.__dict__))

    # download()
    # ____________________________________________________________________________________
    def download(self, file_path=None, verbose=None, ignore_existing=None, checksum=None,
                 destdir=None):
        """Download the file into the current working directory.

        :type file_path: str
        :param file_path: Download file to the given file_path.

        :type ignore_existing: bool
        :param ignore_existing: Overwrite local files if they already
                                exist.

        :type checksum: bool
        :param checksum: Skip downloading file based on checksum.

        """
        verbose = False if verbose is None else verbose
        ignore_existing = False if ignore_existing is None else ignore_existing
        checksum = False if checksum is None else checksum

        file_path = self.name if not file_path else file_path

        if destdir:
            if not os.path.exists(destdir):
                os.mkdir(destdir)
            if os.path.isfile(destdir):
                raise IOError('{} is not a directory!'.format(destdir))
            file_path = os.path.join(destdir, file_path)

        if os.path.exists(file_path):
            if ignore_existing is False and checksum is False:
                raise IOError('file already downloaded: {0}'.format(file_path))
            if checksum:
                md5_sum = utils.get_md5(open(file_path))
                if md5_sum == self.md5:
                    log.info('not downloading file {0}, '
                             'file already exists.'.format(file_path))
                    if verbose:
                        sys.stdout.write(' skipping {0}: already exists.\n'.format(file_path))
                    return

        if verbose:
            sys.stdout.write(' downloading: {0}\n'.format(file_path))
        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        try:
            response = self._item.http_session.get(self.url, stream=True)
            response.raise_for_status()
        except HTTPError as e:
            raise HTTPError('error downloading {0}, {1}'.format(self.url, e))
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
        log.info('downloaded {0}/{1} to {2}'.format(self.identifier,
                                                    self.name.encode('utf-8'),
                                                    file_path))

    # delete()
    # ____________________________________________________________________________________
    def delete(self, debug=False, verbose=False, cascade_delete=False, access_key=None,
               secret_key=None):
        """Delete a file from the Archive. Note: Some files -- such as
        <itemname>_meta.xml -- cannot be deleted.

        :type debug: bool
        :param debug: Set to True to print headers to stdout and exit
                      exit without sending the delete request.

        :type verbose: bool
        :param verbose: Print actions to stdout.

        :type cascade_delete: bool
        :param cascade_delete: Also deletes files derived from the file,
                               and files the file was derived from.
        """
        url = 'http://s3.us.archive.org/{0}/{1}'.format(self.identifier,
                                                        self.name.encode('utf-8'))
        access_key = self._item.session.access_key if not access_key else access_key
        secret_key = self._item.session.secret_key if not secret_key else secret_key
        request = iarequest.S3Request(
            method='DELETE',
            url=url,
            headers={'x-archive-cascade-delete': int(cascade_delete)},
            access_key=access_key,
            secret_key=secret_key
        )
        if debug:
            return request
        else:
            if verbose:
                msg = ' deleting: {0}'.format(self.name.encode('utf-8'))
                if cascade_delete:
                    msg += ' and all derivative files.\n'
                else:
                    msg += '\n'
                sys.stdout.write(msg)
            prepared_request = request.prepare()
            return self._item.http_session.send(prepared_request)
