import time
import json

from boto.s3.connection import S3Connection, OrdinaryCallingFormat

from . import config



# connect()
#_____________________________________________________________________________________
def connect(access_key=None, secret_key=None):
    if not access_key or not secret_key:
        access_key, secret_key = config.get_s3_keys()
    s3_connection = S3Connection(access_key, secret_key,
                                 host='s3.us.archive.org',
                                 calling_format=OrdinaryCallingFormat())
    return s3_connection


# get_bucket()
#_____________________________________________________________________________________
def get_bucket(identifier, s3_connection=None, bucket=None, headers={},
               ignore_bucket=False):
    if not s3_connection:
        s3_connection = connect()
    if ignore_bucket:
        headers['x-archive-ignore-preexisting-bucket'] = 1
        bucket = None
    else:
        if bucket is None:
            bucket = s3_connection.lookup(identifier)
    if bucket:
        return bucket
    bucket = s3_connection.create_bucket(identifier, headers=headers)
    i=0
    while i<60:
        b = s3_connection.lookup(identifier)
        if b:
            return bucket
        time.sleep(10)
        i+=1
    raise NameError('Could not create or lookup {0}'.format(identifier))


# get_headers()
#_____________________________________________________________________________________
def get_headers(metadata, headers={}):
    """Convert a dictionary of metadata into S3 compatible HTTP
    headers, and append headers to ``headers``.

    :type metadata: dict
    :param metadata: Metadata to be converted into S3 HTTP Headers
                     and appended to ``headers``.

    :type headers: dict
    :param headers: (optional) S3 compatible HTTP headers.
    """

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
