import os
from sys import stderr
import json
from contextlib import closing

from requests import Request

from . import __version__, config



# S3Request class
#_____________________________________________________________________________________________
class S3Request(object):

    # __init__()
    #_________________________________________________________________________________________
    def __init__(self, identifier, method=None, local_file=None, remote_name=None, 
                                   metadata={}, headers={}, verbose=False, **kwargs):
        self.endpoint = 'http://s3.us.archive.org/{id}'.format(id=identifier)
        self.local_file = local_file
        self.headers = self._build_headers(metadata, headers, **kwargs) 
        data = None
        if self.local_file:
            if not method:
                method = 'PUT'
            if kwargs.get('auto_make_bucket') != False:
                self.headers['x-archive-auto-make-bucket'] = 1
            if not remote_name:
                remote_name = local_file.name.split('/')[-1]
            self.endpoint += '/{fn}'.format(fn=remote_name)
            chunks = S3Chunks(self.local_file, remote_name,
                              file_size=self.headers.get('x-archive-size-hint'),
                              chunk_size=1024)
            data = IterableToFileAdapter(chunks)
        #self.request = Request(method, self.endpoint, data=data, headers=self.headers)
        self.request = Request(method, self.endpoint, hooks=dict(data=self.h), headers=self.headers)

    def h():
        with closing(data) as file:
            while True:
                data = file.read(self.chunk_size)
                if not data:
                    stderr.write("\r uploading file: {fn} (100%)\n".format(fn=self.remote_name))
                    break
                self.readsofar += len(data)
                percent = self.readsofar * 1e2 / self.total_size
                stderr.write(
                    "\r uploading file: {fn} ({percent:3.0f}%)".format(percent=percent,
                                                                       fn=self.remote_name))
                yield data
        

    # _build_headers()
    #_________________________________________________________________________________________
    def _build_headers(self, metadata={}, headers={}, **kwargs):
        """Convert a dictionary of metadata into S3 compatible HTTP
        headers, and append headers to ``headers``.
    
        :type metadata: dict
        :param metadata: Metadata to be converted into S3 HTTP Headers
                         and appended to ``headers``.
    
        :type headers: dict
        :param headers: (optional) S3 compatible HTTP headers.
    
        """
        if not kwargs.get('access_key') or not kwargs.get('secret_key'):
            access_key, secret_key = config.get_s3_keys()
        else:
            access_key = kwargs.get('access_key')
            secret_key = kwargs.get('secret_key')
        headers['Authorization'] = 'LOW {0}:{1}'.format(access_key, secret_key)
        scanner = 'Internet Archive Python library {0}'.format(__version__)
        headers['x-archive-meta-scanner'] = scanner
        if kwargs.get('auto_make_bucket'):
            headers['x-archive-auto-make-bucket'] = 1
        if kwargs.get('ignore_bucket') == True:
            headers['x-archive-ignore-preexisting-bucket'] = 1
        if kwargs.get('queue_derive') == False:
            headers['x-archive-queue-derive'] = 0

        # Attempt to add size-hint header.
        if not headers.get('x-archive-size-hint'):
            try:
                self.local_file.seek(0, os.SEEK_END)
                headers['x-archive-size-hint'] = self.local_file.tell()
                self.local_file.seek(0, os.SEEK_SET)
            except IOError:
                pass
    
        for meta_key, meta_value in metadata.iteritems():
    
            # Encode arrays into JSON strings because Archive.org does not 
            # yet support complex metadata structures in 
            # <identifier>_meta.xml.
            if isinstance(meta_value, dict):
                meta_value = json.dumps(meta_value)
    
            # Convert the metadata value into a list if it is not already
            # iterable.
            if not hasattr(meta_value, '__iter__'):
                    meta_value = [meta_value]
    
            # Convert metadata items into HTTP headers and add to 
            # ``headers`` dict.
            for i, value in enumerate(meta_value):
                if not value:
                    continue
                s3_header_key = 'x-archive-meta{0:02d}-{1}'.format(i, meta_key)
    
                # because rfc822 http headers disallow _ in names, IA-S3 will
                # translate two hyphens in a row (--) into an underscore (_).
                s3_header_key = s3_header_key.replace('_', '--')
                try:
                    if not headers.get(s3_header_key):
                        headers[s3_header_key] = value.encode('utf-8')
                except AttributeError:
                    if not headers.get(s3_header_key):
                        headers[s3_header_key] = value
    
        return dict((k,v) for k,v in headers.items())

    # prepare()
    #_________________________________________________________________________________________
    def prepare(self):
        return self.request.prepare()


# S3Chunks class
#_____________________________________________________________________________________________
class S3Chunks(object):
    def __init__(self, local_file, remote_name, file_size=0, chunk_size=1024):
        self.local_file = local_file
        self.chunk_size = chunk_size
        self.total_size = file_size
        self.remote_name = remote_name
        self.readsofar = 0

    def __iter__(self):
        # `contextlib.closing()` is used to make StringIO work with
        # `with` statement.
        with closing(self.local_file) as file:
            while True:
                data = file.read(self.chunk_size)
                if not data:
                    stderr.write("\r uploading file: {fn} (100%)\n".format(fn=self.remote_name))
                    break
                self.readsofar += len(data)
                percent = self.readsofar * 1e2 / self.total_size
                stderr.write(
                    "\r uploading file: {fn} ({percent:3.0f}%)".format(percent=percent,
                                                                       fn=self.remote_name))
                yield data

    def __len__(self):
        return self.total_size


# IterableToFileAdapter class
#_____________________________________________________________________________________________
class IterableToFileAdapter(object):
    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.length = len(iterable)

    def read(self, size=-1): # TBD: add buffer for `len(data) > size` case
        return next(self.iterator, b'')

    def __len__(self):
        return self.length
