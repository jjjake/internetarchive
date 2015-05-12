import os
import sys
from fnmatch import fnmatch
import logging
import time

from requests.exceptions import HTTPError
from requests import Response
from clint.textui import progress
import six
import six.moves.urllib as urllib

from . import iarequest, utils
from .session import ArchiveSession
from .files import File
from . import __version__

log = logging.getLogger(__name__)


class BaseItem(object):
    def __init__(self, item_metadata):
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

        for key in item_metadata:
            setattr(self, key, item_metadata[key])

        self.item_metadata = item_metadata
        self.identifier = self.metadata.get('identifier')
        self.exists = True if self.item_metadata else False


# Item class
# ________________________________________________________________________________________
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
    def __init__(self, item_metadata, archive_session=None, **kwargs):
        self.session = archive_session if archive_session else ArchiveSession(**kwargs)
        super(Item, self).__init__(item_metadata)

    # __repr__()
    # ____________________________________________________________________________________
    def __repr__(self):
        return ('Item(identifier={identifier!r}, '
                'exists={exists!r})'.format(**self.__dict__))

    # file()
    # ____________________________________________________________________________________
    def get_file(self, file_name):
        """Get a :class:`File <File>` object for the named file.

        :rtype: :class:`internetarchive.File <File>`
        :returns: An :class:`internetarchive.File <File>` object.
        """
        return File(self, file_name)

    # get_files()
    # ____________________________________________________________________________________
    def get_files(self, files=None, source=None, formats=None, glob_pattern=None):
        files = [] if not files else files
        source = [] if not source else source
        formats = [] if not formats else formats

        if not isinstance(files, (list, tuple, set)):
            files = [files]
        if not isinstance(source, (list, tuple, set)):
            source = [source]
        if not isinstance(formats, (list, tuple, set)):
            formats = [formats]

        if not any(k for k in [files, source, formats, glob_pattern]):
            for f in self.files:
                yield self.get_file(f.get('name'))

        for f in self.files:
            if f.get('name') in files:
                yield self.get_file(f.get('name'))
            elif f.get('source') in source:
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

    # download()
    # ____________________________________________________________________________________
    def download(self,
                 files=None,
                 source=None,
                 formats=None,
                 glob_pattern=None,
                 dry_run=None,
                 clobber=None,
                 no_clobber=None,
                 checksum=None,
                 destdir=None,
                 no_directory=None,
                 verbose=None,
                 debug=None):
        """Download files from an item.

        :param files: (optional) Only download files matching given file names.

        :type source: str
        :param source: (optional) Only download files matching given source.

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
        dry_run = False if not dry_run else True
        clobber = False if not clobber else True
        checksum = False if not checksum else True
        no_directory = False if not no_directory else True
        verbose = False if not verbose else True
        debug = False if not debug else True

        if verbose:
            sys.stderr.write('{0}:\n'.format(self.identifier))
            if self.item_metadata.get('is_dark') is True:
                sys.stderr.write(' skipping: item is dark.\n')
                return
            elif self.metadata == {}:
                sys.stderr.write(' skipping: item does not exist.\n')
                return

        responses = []
        for f in self.get_files(files, source, formats, glob_pattern):
            fname = f.name.encode('utf-8')
            if no_directory:
                path = fname
            else:
                path = os.path.join(self.identifier, fname)
            if dry_run:
                sys.stdout.write(f.url + '\n')
                continue
            try:
                r = f.download(path, clobber, checksum, destdir, verbose, debug)
                responses.append(r)
            except IOError as exc:
                if no_clobber:
                    if verbose:
                        sys.stderr.write(' {}\n'.format(exc))
                else:
                    raise (exc)
        return responses

    # modify_metadata()
    # ____________________________________________________________________________________
    def modify_metadata(self, metadata,
                        target=None,
                        append=None,
                        priority=None,
                        access_key=None,
                        secret_key=None,
                        debug=None):
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

        url = '{protocol}//archive.org/metadata/{identifier}'.format(
            protocol=self.session.protocol,
            identifier=self.identifier)
        request = iarequest.MetadataRequest(
            url=url,
            metadata=metadata,
            source_metadata=self.item_metadata.get(target.split('/')[0], {}),
            target=target,
            priority=priority,
            access_key=access_key,
            secret_key=secret_key,
            append=append, )
        if debug:
            return request
        prepared_request = request.prepare()
        resp = self.session.send(prepared_request)
        item_metadata = self.session.get_metadata(self.identifier)
        # Re-initialize the Item object with the updated metadata.
        self.__init__(item_metadata, archive_session=self.session)
        return resp

    # upload_file()
    # ____________________________________________________________________________________
    def upload_file(self, body,
                    key=None,
                    metadata=None,
                    headers=None,
                    access_key=None,
                    secret_key=None,
                    queue_derive=True,
                    verbose=False,
                    verify=True,
                    checksum=False,
                    delete=False,
                    retries=None,
                    retries_sleep=None,
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
        checksum = True if delete or checksum else False

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
        base_url = '{protocol}//s3.us.archive.org/{identifier}'.format(
            protocol=self.session.protocol,
            identifier=self.identifier)
        url = '{base_url}/{key}'.format(base_url=base_url,
                                        key=urllib.parse.quote(key.lstrip('/')))

        # Skip based on checksum.
        md5_sum = utils.get_md5(body)
        ia_file = self.get_file(key)
        if (checksum) and (not self.tasks) and (ia_file) and (ia_file.md5 == md5_sum):
            log.info('{f} already exists: {u}'.format(f=key, u=url))
            if verbose:
                sys.stderr.write(' {f} already exists, skipping.\n'.format(f=key))
            if delete:
                log.info(
                    '{f} successfully uploaded to https://archive.org/download/{i}/{f} '
                    'and verified, deleting '
                    'local copy'.format(i=self.identifier,
                                        f=key))
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
                    expected_size = size / chunk_size + 1
                    chunks = utils.chunk_generator(body, chunk_size)
                    progress_generator = progress.bar(
                        chunks,
                        expected_size=expected_size,
                        label=' uploading {f}: '.format(f=key))
                    data = utils.IterableToFileAdapter(progress_generator, size)
                except:
                    sys.stderr.write(' uploading {f}: '.format(f=key))
                    data = body
            else:
                data = body

            request = iarequest.S3Request(method='PUT',
                                          url=url,
                                          headers=headers,
                                          data=data,
                                          metadata=metadata,
                                          access_key=access_key,
                                          secret_key=secret_key,
                                          queue_derive=queue_derive, **kwargs)
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
                            time.sleep(retries_sleep)
                            log.info(error_msg)
                            if verbose:
                                sys.stderr.write(' warning: {0}\n'.format(error_msg))
                            retries -= 1
                            continue
                    request = _build_request()
                    prepared_request = request.prepare()
                    response = self.session.send(prepared_request, stream=True)
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
                        'local copy'.format(i=self.identifier,
                                            f=key))
                    os.remove(body.name)
                return response
            except HTTPError as exc:
                error_msg = (' error uploading {0} to {1}, '
                             '{2}'.format(key, self.identifier, exc))
                log.error(error_msg)
                raise

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
                    key = str(key)
                resp = self.upload_file(body, key=key, **kwargs)
                responses.append(resp)
        return responses
