try:
    import ujson as json
except ImportError:
    import json
import urllib
import os
import sys
import httplib
import urllib2
import fnmatch

import jsonpatch
import boto
from cStringIO import StringIO

from . import __version__, ias3, config, utils



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
        self.metadata_timeout = metadata_timeout
        self.s3_connection = None
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
        for file_dict in self.metadata['files']:
            if file_dict['name'] == name:
                return File(self, file_dict)


    # download()
    #_____________________________________________________________________________________
    def download(self, concurrent=False, source=None, formats=None, glob_pattern=None,
                 ignore_existing=False):
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
            files = [f for f in files if fnmatch.fnmatch(f.name, glob_pattern)]

        for f in files:
            fname = f.name.encode('utf-8')
            path = os.path.join(self.identifier, fname)
            sys.stdout.write('downloading: {0}\n'.format(fname))
            if concurrent:
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

        json_patch = jsonpatch.make_patch(src, dest).patch
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
                    derive=True, ignore_bucket=False, multipart=False,
                    bytes_per_chunk=16777216, debug=False):
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

        :type derive: bool
        :param derive: (optional) Set to False to prevent an item from
                       being derived after upload.

        :type multipart: bool
        :param multipart: (optional) Set to True to upload files in
                          parts. Useful when uploading large files.

        :type ignore_bucket: bool
        :param ignore_bucket: (optional) Set to True to ignore and
                              clobber existing files and metadata.

        :type debug: bool
        :param debug: (optional) Set to True to print headers to stdout,
                      and exit without sending the upload request.

        :type bytes_per_chunk: int
        :param bytes_per_chunk: (optional) Used to determine the chunk
                                size when using multipart upload.

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

        if not hasattr(local_file, 'read'):
            local_file = open(local_file, 'rb')
        if not remote_name:
            remote_name = local_file.name.split('/')[-1]

        headers = ias3.get_headers(metadata, headers)
        scanner = 'Internet Archive Python library {0}'.format(__version__)
        headers['x-archive-meta-scanner'] = scanner
        header_names = [header_name.lower() for header_name in headers.keys()]
        if 'x-archive-size-hint' not in header_names:
            try:
                local_file.seek(0, os.SEEK_END)
                headers['x-archive-size-hint'] = local_file.tell()
                local_file.seek(0, os.SEEK_SET)
            except IOError:
                pass

        if not self.s3_connection:
            self.s3_connection = ias3.connect()
        if not self.bucket:
            self.bucket = ias3.get_bucket(self.identifier,
                                          s3_connection=self.s3_connection,
                                          headers=headers,
                                          ignore_bucket=ignore_bucket)

        if not derive:
            headers['x-archive-queue-derive'] =  0

        # Don't clobber existing files unless ignore_bucket is True.
        if self.bucket.get_key(remote_name) and not ignore_bucket:
            return True

        if not multipart:
            k = boto.s3.key.Key(self.bucket)
            k.name = remote_name
            k.set_contents_from_file(local_file, headers=headers)
        else:
            mp = self.bucket.initiate_multipart_upload(remote_name, headers=headers)
            def read_chunk():
                return local_file.read(bytes_per_chunk)
            part = 1
            for chunk in iter(read_chunk, ''):
                part_fp = StringIO(chunk)
                mp.upload_part_from_file(part_fp, part_num=part)
                part += 1
            mp.complete_upload()
        return True


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
            >>> item.upload('/path/to/image.jpg', metadata=md, derive=False)
            True

        :rtype: bool
        :returns: True if the request was successful and all files were
                  uploaded, False otherwise.

        """

        if kwargs.get('debug'):
            return ias3.get_headers(kwargs.get('metadata', {}), kwargs.get('headers', {}))
        if not isinstance(files, (list, tuple)):
            files = [files]
        for local_file in files:
            # Directory support.
            if isinstance(local_file, basestring) and os.path.isdir(local_file):
                for path, dir, files in os.walk(local_file):
                    for f in files:
                        remote_name = os.path.join(path, f)
                        local_file = os.path.relpath(remote_name, local_file)
                        response = self.upload_file(remote_name, 
                                                    remote_name=remote_name, 
                                                    **kwargs)
            else:
                response = self.upload_file(local_file, **kwargs)
            if not response:
                return False
        return True


# File class
#_________________________________________________________________________________________
class File(object):
    """:todo: document File class."""

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
        if file_path is None:
            file_path = self.name

        if os.path.exists(file_path) and not ignore_existing:
            raise IOError('File already exists: {0}'.format(file_path))

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        fname = self.name.encode('utf-8')
        url = '{0}/{1}'.format(self.item.download_url, fname)
        #urllib.urlretrieve(url, file_path)

        # Add cookies to request when downloading to allow privileged
        # users the ability to download access-restricted files.
        logged_in_user, logged_in_sig = config.get_cookies()
        cookies = ('logged-in-user={0}; '
                   'logged-in-sig={1}'.format(logged_in_user, logged_in_sig))

        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie', cookies))
        data = opener.open(url)
        with open(file_path, 'wb') as fp:
            fp.write(data.read())
