try:
    import ujson as json
except ImportError:
    import json
import urllib
import os
from sys import stdout
import httplib
import urllib2
from fnmatch import fnmatch
from requests import Request, Session
from contextlib import closing

from jsonpatch import make_patch

from . import ias3, config, utils



# Item class
#_________________________________________________________________________________________
class Item(object):
    """This class represents an archive.org item. You can use this
    class to access item metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> print item.metadata

    Or to modify the metadata for an item::

        >>> metadata = dict(title='The Stairs'))
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
        self.identifier = identifier
        self.secure = secure
        if secure:
            protocol = 'https'
        else:
            protocol = 'http'
        self.details_url = '{0}://archive.org/details/{1}'.format(protocol, identifier)
        self.download_url = '{0}://archive.org/download/{1}'.format(protocol, identifier)
        self.metadata_url = '{0}://archive.org/metadata/{1}'.format(protocol, identifier)
        self.s3_endpoint = '{0}://s3.us.archive.org/{1}'.format(protocol, identifier)
        self.metadata_timeout = metadata_timeout
        self.session = None
        self.bucket = None
        self.metadata = utils.get_item_metadata(identifier, metadata_timeout, secure)
        if self.metadata == {}:
            self.exists = False
        else:
            self.exists = True


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


    # files()
    #_____________________________________________________________________________________
    def files(self):
        """Generator for iterating over files in an item.

        :rtype: generator
        :returns: A generator that yields :class:`internetarchive.File
                  <File>` objects.

        """
        for file_dict in self.metadata.get('files', []):
            file = File(self, file_dict)
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
                return File(self, file_dict)


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
            if verbose:
                stdout.write('downloading: {0}\n'.format(fname))
            if dry_run:
                stdout.write('{0}\n'.format(f.download_url))
            elif concurrent:
                pool.spawn(f.download, path, ignore_existing=ignore_existing)
            else:
                f.download(path, ignore_existing=ignore_existing)
        if concurrent:
            pool.join()
        return True


    # modify_metadata()
    #_____________________________________________________________________________________
    def modify_metadata(self, metadata, target='metadata'):
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
        dest = dict((src.items() + metadata.items()))

        # Prepare patch to remove metadata elements with the value: "REMOVE_TAG".
        for k,v in metadata.items():
            if v == 'REMOVE_TAG' or not v:
                del dest[k]

        json_patch = make_patch(src, dest).patch
        # Reformat patch to be compliant with version 02 of the Json-Patch standard.
        patch = []
        for p in json_patch:
            pd = {p['op']: p['path']}
            if p['op'] != 'remove':
                pd['value'] = p['value']
            patch.append(dict((k,v) for k,v in pd.items() if v))

        data = {
            '-patch': json.dumps(patch),
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
        self.metadata = utils.get_item_metadata(self.identifier, self.metadata_timeout,
                                                self.secure)
        return dict(
            status_code = status_code,
            content = json.loads(resp_file.read()),
        )


    # upload_file()
    #_____________________________________________________________________________________
    def upload_file(self, local_file, remote_name=None, metadata={}, headers={},
                    queue_derive=True, ignore_bucket=False, verbose=False, debug=False):
        """Upload a single file to an item. The item will be created
        if it does not exist.

        :type local_file: str or file
        :param local_file: The filepath or file-like object to be uploaded.

        :type remote_name: str
        :param remote_name: (optional) Sets the remote filename.

        :type metadata: dict
        :param metadata: (optional) Metadata used to create a new item.

        :type headers: dict
        :param headers: (optional) Add additional IA-S3 headers to
                        request.

        :type queue_derive: bool
        :param queue_derive: (optional) Set to False to prevent an item from
                             being derived after upload.

        :type ignore_bucket: bool
        :param ignore_bucket: (optional) Set to True to ignore and
                              clobber existing files and metadata.

        :type debug: bool
        :param debug: (optional) Set to True to print headers to stdout,
                      and exit without sending the upload request.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> item.upload_file('/path/to/image.jpg',
            ...                  remote_name='photos/image1.jpg')
            True

        :rtype: bool
        :returns: True if the request was successful and file was
                  uploaded, False otherwise.

        """
        if not self.session:
            self.session = Session()

        if not hasattr(local_file, 'read'):
            local_file = open(local_file, 'rb')
        if not remote_name:
            remote_name = local_file.name.split('/')[-1]

        # Attempt to add size-hint header.    
        if not headers.get('x-archive-size-hint'):
            try:
                local_file.seek(0, os.SEEK_END)
                headers['x-archive-size-hint'] = local_file.tell()
                local_file.seek(0, os.SEEK_SET)
            except IOError:
                pass

        # Prepare Request.
        endpoint = 'http://s3.us.archive.org/{0}/{1}'.format(self.identifier, remote_name)
        headers = ias3.build_headers(metadata, headers, queue_derive=queue_derive,
                                     ignore_bucket=ignore_bucket)
        request = Request('PUT', endpoint, headers=headers)
        # TODO: Add support for multipart.
        # `contextlib.closing()` is used to make StringIO work with 
        # `with` statement.
        with closing(local_file) as data:
            request.data = data.read()
        prepped_request = request.prepare()

        if debug:
            return prepped_request 
        else:
            if verbose:
                stdout.write(' uploading file: {0}\n'.format(remote_name))
            return self.session.send(prepped_request)


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
                    remote_name = os.path.relpath(filepath, directory)
                    yield (filepath, remote_name)

        if not isinstance(files, (list, tuple)):
            files = [files]

        responses = []
        for local_file in files:
            if isinstance(local_file, basestring) and os.path.isdir(local_file):
                for local_file, remote_name in iter_directory(local_file):
                    resp = self.upload_file(local_file, remote_name=remote_name, **kwargs)
                    responses.append(resp)
            else:
                resp = self.upload_file(local_file, **kwargs)
                responses.append(resp)
        return responses


# File class
#_________________________________________________________________________________________
class File(object):
    """:todo: document ``internetarchive.File`` class."""
    # init()
    #_____________________________________________________________________________________
    def __init__(self, item, file_dict):
        self.item = item
        self.external_identifier = file_dict.get('external-identifier')
        self.name = file_dict.get('name')
        self.source = file_dict.get('source')
        self.size = file_dict.get('size')
        self.size = file_dict.get('size')
        if self.size is not None:
            self.size = int(self.size)
        self.format = file_dict.get('format')
        self.mtime = file_dict.get('mtime')
        self.md5  = file_dict.get('md5')
        self.sha1 = file_dict.get('crc32')
        self.sha1 = file_dict.get('sha1')
        self.fname = self.name.encode('utf-8')
        self.download_url = '{0}/{1}'.format(self.item.download_url, 
                                             urllib.quote(self.fname, safe=''))
        if not self.item.session:
            self.item.session = Session()


    # __repr__()
    #_____________________________________________________________________________________
    def __repr__(self):
        return ('File(identifier={item.identifier!r}, '
                'filename={name!r}, '
                'size={size!r}, '
                'source={source!r}, '
                'format={format!r})'.format(**self.__dict__))


    # download()
    #_____________________________________________________________________________________
    def download(self, file_path=None, ignore_existing=False):
        """:todo: document ``internetarchive.File.download()`` method"""
        if file_path is None:
            file_path = self.name

        if os.path.exists(file_path) and not ignore_existing:
            raise IOError('File already exists: {0}'.format(file_path))

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        # Add cookies to request when downloading to allow privileged
        # users the ability to download access-restricted files.
        logged_in_user, logged_in_sig = config.get_cookies()
        cookies = ('logged-in-user={0}; '
                   'logged-in-sig={1}'.format(logged_in_user, logged_in_sig))

        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie', cookies))
        data = opener.open(self.download_url)
        with open(file_path, 'wb') as fp:
            fp.write(data.read())

             
    # delete()
    #_____________________________________________________________________________________
    def delete(self, debug=False, verbose=False, cascade_delete=False):
        if cascade_delete:
            headers = ias3.build_headers(headers={'x-archive-cascade-delete': 1})
        else:
            headers = ias3.build_headers()
        endpoint = '{0}/{1}'.format(self.item.s3_endpoint, self.fname)
        prepped_request = Request('DELETE', endpoint, headers=headers).prepare()
        if debug:
            return prepped_request 
        else:
            if verbose:
                stdout.write(' deleting file: {0}\n'.format(self.name))
            return self.item.session.send(prepped_request)
