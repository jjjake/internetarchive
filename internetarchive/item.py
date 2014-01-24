try:
    import ujson as json
except ImportError:
    import json
import urllib
import os
from sys import stdout
import httplib
from fnmatch import fnmatch
from requests import Request, Session
from requests.exceptions import ConnectionError, HTTPError
from clint.textui import progress

from jsonpatch import make_patch

from . import s3, config, __version__, utils



# Item class
#_________________________________________________________________________________________
class Item(object):
    """This class represents an archive.org item. You can use this
    class to access item metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> print item.metadata

    Or to modify the metadata for an item::

        >>> metadata = dict(title='The Stairs')
        >>> item.modify(metadata)
        >>> print item.metadata['metadata']['title']
        u'The Stairs'

    This class also uses IA's S3-like interface to upload files to an
    item. You need to supply your IAS3 credentials in environment
    variables in order to upload::

        >>> import os
        >>> os.environ['AWS_ACCESS_KEY_ID'] = 'Y6oUrAcCEs4sK8ey'
        >>> os.environ['AWS_SECRET_ACCESS_KEY'] = 'youRSECRETKEYzZzZ'
        >>> item.upload('myfile.tar')
        True

    You can retrieve S3 keys here: `https://archive.org/account/s3.php
    <https://archive.org/account/s3.php>`__

    """
    # init()
    #_____________________________________________________________________________________
    def __init__(self, identifier, metadata_timeout=None, secure=False):
        """
        :type identifier: str
        :param identifier: The globally unique Archive.org identifier
                           for a given item.

        :type metadata_timeout: int
        :param metadata_timeout: (optional) Set a timeout for retrieving 
                                 an item's metadata.

        :type secure: bool
        :param secure: (optional) If secure is True, use HTTPS protocol, 
                       otherwise use HTTP.

        """
        self.secure = secure
        protocol = 'https://' if secure else 'http://'
        self.host = protocol + 'archive.org'
        self.identifier = identifier
        self.details_url = self.host + '/details/' + self.identifier
        self.download_url = self.host + '/download/' + self.identifier
        self.metadata_url = self.host + '/metadata/' + self.identifier
        self.s3_endpoint = protocol + 's3.us.archive.org' + self.identifier
        self.metadata_timeout = metadata_timeout
        self.session = None
        self.metadata = self.get_metadata()
        self.exists = False if self.metadata == {} else True


    # __repr__()
    #_____________________________________________________________________________________
    def __repr__(self):
        item_description = dict(
                    identifier = self.identifier,
                    exists = self.exists,
                    item_size = self.metadata.get('item_size'),
                    files_count = self.metadata.get('files_count'),
        )
        return ('Item(identifier={identifier!r}, '
                'exists={exists!r}, '
                'item_size={item_size!r}, '
                'files_count={files_count!r})'.format(**item_description))


    # get_metadata()
    #_____________________________________________________________________________________
    def get_metadata(self, target=None):
        """Get an item's metadata from the `Metadata API 
        <http://blog.archive.org/2013/07/04/metadata-api/>`__

        :type identifier: str
        :param identifier: Globally unique Archive.org identifier.

        :type target: bool
        :param target: (optional) Metadata target to retrieve.

        :rtype: dict
        :returns: Metadat API response.

        """
        if not self.session:
            self.session = Session()
        response = self.session.get(self.metadata_url, timeout=self.metadata_timeout)
        if response.status_code != 200:
            raise ConnectionError("Unable connect to Archive.org "
                                  "({0})".format(response.status_code))
        metadata = response.json()
        if target:
            metadata = metadata.get(target, {})
        return metadata


    # files()
    #_____________________________________________________________________________________
    def files(self):
        """Generator for iterating over files in an item.

        :rtype: generator
        :returns: A generator that yields :class:`internetarchive.File
                  <File>` objects.

        """
        for file_dict in self.metadata.get('files', []):
            file = File(self.__dict__, file_dict)
            yield file


    # file()
    #_____________________________________________________________________________________
    def file(self, name):
        """Get a :class:`File <File>` object for the named file.

        :rtype: :class:`internetarchive.File <File>`
        :returns: An :class:`internetarchive.File <File>` object.

        """
        for file_dict in self.metadata.get('files', []):
            if file_dict.get('name') == name:
                return File(self.__dict__, file_dict)


    # download()
    #_____________________________________________________________________________________
    def download(self, concurrent=False, source=None, formats=None, glob_pattern=None,
                 dry_run=False, verbose=False, ignore_existing=False):
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

        :rtype: bool
        :returns: True if if files have been downloaded successfully.

        """
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

        files = self.files()
        if source:
            if type(source) == str:
                source = [source]
            files = [f for f in files if f.source in source]
        if formats:
            if type(formats) == str:
                formats = [formats]
            files = [f for f in files if f.format in formats]
        if glob_pattern:
            files = [f for f in files if fnmatch(f.name, glob_pattern)]

        for f in files:
            fname = f.name.encode('utf-8')
            path = os.path.join(self.identifier, fname)
            if dry_run:
                stdout.write(f.url + '\n')
                continue
            if verbose:
                stdout.write(' downloading: {0}\n'.format(fname))
            if concurrent:
                pool.spawn(f.download, path, ignore_existing=ignore_existing)
            else:
                f.download(path, ignore_existing=ignore_existing)
        if concurrent:
            pool.join()
        return True


    # modify_metadata()
    #_____________________________________________________________________________________
    def modify_metadata(self, metadata, target='metadata', append=False):
        """Modify the metadata of an existing item on Archive.org.

        Note: The Metadata Write API does not yet comply with the
        latest Json-Patch standard. It currently complies with `version 02
        <https://tools.ietf.org/html/draft-ietf-appsawg-json-patch-02>`__.

        :type metadata: dict
        :param metadata: Metadata used to update the item.

        :type target: str
        :param target: (optional) Set the metadata target to update.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('mapi_test_item1')
            >>> md = dict(new_key='new_value', foo=['bar', 'bar2'])
            >>> item.modify_metadata(md)

        :rtype: dict
        :returns: A dictionary containing the status_code and response
                  returned from the Metadata API.

        """
        access_key, secret_key = config.get_s3_keys()
        src = self.metadata.get(target, {})
        dest = src.copy()
        dest.update(metadata)

        # Prepare patch to remove metadata elements with the value: "REMOVE_TAG".
        for key, val in metadata.items():
            if val == 'REMOVE_TAG' or not val:
                del dest[key]
            if append:
                dest[key] = '{0} {1}'.format(src[key], val)

        json_patch = make_patch(src, dest).patch

        data = {
            '-patch': json.dumps(json_patch),
            '-target': target,
            'access': access_key,
            'secret': secret_key,
        }

        host = 'archive.org'
        path = '/metadata/{0}'.format(self.identifier)
        http = httplib.HTTP(host)
        http.putrequest("POST", path)
        http.putheader("Host", host)
        data = urllib.urlencode(data)
        http.putheader("Content-Type", 'application/x-www-form-urlencoded')
        http.putheader("Content-Length", str(len(data)))
        http.endheaders()
        http.send(data)
        status_code, error_message, headers = http.getreply()
        resp_file = http.getfile()
        self.metadata = self.get_metadata()
        return dict(
            status_code = status_code,
            content = json.loads(resp_file.read()),
        )


    # upload_file()
    #_____________________________________________________________________________________
    def upload_file(self, body, key=None, metadata={}, headers={},
                    access_key=None, secret_key=None, queue_derive=True, 
                    ignore_preexisting_bucket=False, verbose=False, debug=False):
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

        key = body.name.split('/')[-1] if key is None else key
        url = 'http://s3.us.archive.org/{0}/{1}'.format(self.identifier, key) 
        headers = s3.build_headers(metadata=metadata, 
                                   headers=headers, 
                                   queue_derive=queue_derive,
                                   auto_make_bucket=True,
                                   size_hint=size,
                                   ignore_preexisting_bucket=ignore_preexisting_bucket)
        if verbose:
            try:
                chunk_size = 1024
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

        request = Request(
            method='PUT',
            url=url,
            headers=headers,
            data=data,
            auth=s3.BasicAuth(access_key, secret_key),
        )
        
        if debug:
            return request
        else:
            if not self.session:
                self.session = Session()
            prepared_request = request.prepare()
            return self.session.send(prepared_request, stream=True)


    # upload()
    #_____________________________________________________________________________________
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

        if not isinstance(files, (list, tuple)):
            files = [files]

        responses = []
        for f in files:
            key = None
            if isinstance(f, basestring) and os.path.isdir(f):
                for filepath, key in iter_directory(f):
                    resp = self.upload_file(filepath, key=key, **kwargs)
                    responses.append(resp)
            else:
                resp = self.upload_file(f, **kwargs)
                responses.append(resp)
        return responses


# File class
#_________________________________________________________________________________________
class File(object):
    """:todo: document ``internetarchive.File`` class."""
    # init()
    #_____________________________________________________________________________________
    def __init__(self, item_dict, file_dict):
        self.identifier = item_dict['identifier']
        self.external_identifier = file_dict.get('external-identifier')
        self.name = file_dict.get('name')
        self.source = file_dict.get('source')
        self.size = file_dict.get('size')
        self.format = file_dict.get('format')
        self.mtime = file_dict.get('mtime')
        self.md5  = file_dict.get('md5')
        self.crc32 = file_dict.get('crc32')
        self.sha1 = file_dict.get('sha1')
        self.fname = self.name.encode('utf-8')
        self.length = file_dict.get('length')
        self.url = item_dict.get('download_url') + '/' + urllib.quote(self.fname, safe='')
        self.session = item_dict.get('session') if item_dict.get('session') else Session()


    # __repr__()
    #_____________________________________________________________________________________
    def __repr__(self):
        return ('File(identifier={identifier!r}, '
                'filename={name!r}, '
                'size={size!r}, '
                'source={source!r}, '
                'format={format!r})'.format(**self.__dict__))


    # download()
    #_____________________________________________________________________________________
    def download(self, file_path=None, ignore_existing=False):
        """:todo: document ``internetarchive.File.download()`` method"""
        file_path = self.name if not file_path else file_path
        if os.path.exists(file_path) and not ignore_existing:
            raise IOError('File already exists: {0}'.format(file_path))

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        if not self.session:
            self.session = Session()
        self.session.cookies = config.get_cookiejar()

        try:
            response = self.session.get(self.url, stream=True)
            response.raise_for_status()
        except HTTPError as e:
            raise HTTPError('Error downloading {0}, {1}'.format(self.url, e))
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()

             
    # delete()
    #_____________________________________________________________________________________
    def delete(self, debug=False, verbose=False, cascade_delete=False):
        headers = s3.build_headers(cascade_delete=cascade_delete)
        url = 'http://s3.us.archive.org/{0}/{1}'.format(self.identifier, self.fname)
        access_key, secret_key = config.get_s3_keys()
        request = Request(
            method='DELETE', 
            url=url, 
            headers=headers,
            auth=s3.BasicAuth(access_key, secret_key),
        )
        if debug:
            return request 
        else:
            if verbose:
                stdout.write(' deleting file: {0}\n'.format(self.name))
            prepared_request = request.prepare()
            return self.session.send(prepared_request)
