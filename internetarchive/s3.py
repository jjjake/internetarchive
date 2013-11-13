from sys import stderr
import json
from contextlib import closing

from . import config



# Chunks class
#_____________________________________________________________________________________________
class Chunks(object):
    def __init__(self, fileobj, key=None, file_size=0, chunk_size=1024, verbose=False):
        self.fileobj = fileobj
        self.total_size = file_size
        self.chunk_size = chunk_size
        self.key = fileobj.name.split('/')[-1] if key is None else key
        self.readsofar = 0
        self.verbose = verbose

    def __iter__(self):
        # `contextlib.closing()` is used to make StringIO work with
        # `with` statement.
        with closing(self.fileobj) as file:
            while True:
                data = file.read(self.chunk_size)
                if not data:
                    if self.verbose:
                        stderr.write("\r uploading file: {0} (100%)\n".format(self.key))
                    break
                self.readsofar += len(data)
                percent = self.readsofar * 1e2 / self.total_size
                if self.verbose:
                    stderr.write( 
                        "\r uploading file: {0} ({1:3.0f}%)".format(self.key, percent)
                    )
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


# build_headers()
#_________________________________________________________________________________________
def build_headers(**kwargs):
    """Convert a dictionary of metadata into S3 compatible HTTP
    headers, and append headers to ``headers``.

    :type metadata: dict
    :param metadata: Metadata to be converted into S3 HTTP Headers
                     and appended to ``headers``.

    :type headers: dict
    :param headers: (optional) S3 compatible HTTP headers.

    """
    metadata = {} if not kwargs.get('metadata') else kwargs.get('metadata')
    headers = {} if not kwargs.get('headers') else kwargs.get('headers')

    access_key, secret_key = (kwargs.get('access_key'), kwargs.get('secret_key'))
    if not access_key or not secret_key:
        access_key, secret_key = config.get_s3_keys()
    headers['Authorization'] = 'LOW {0}:{1}'.format(access_key, secret_key)

    # Convert kwargs into S3 Headers.
    for key, value in kwargs.items():
        if key in ['access_key', 'secret_key']:
            continue
        if value is True:
            value = 1
        if value is False:
            value = 0
        key = 'x-archive-{key}'.format(key=key.replace('_', '-'))
        headers[key] = value

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
