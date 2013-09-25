import time

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

    def encode_s3_header(header_key, header_value):
        # because rfc822 http headers disallow _ in names, IA-S3 will
        # translate two hyphens in a row (--) into an underscore (_).
        header_key = header_key.replace('_', '--')
        try:
            encoded_header_key = header_key.encode('utf-8')
            encoded_header_value = header_value.encode('utf-8')
        except AttributeError:
            encoded_header_key = header_key
            encoded_header_value = header_value
        return (encoded_header_key, encoded_header_value)

    for meta_key, meta_value in metadata.iteritems():
        try:
            # Convert metadata items into multiple header fields if
            # the item's value is iterable, and append to the
            # headers dict.
            if isinstance(meta_value, basestring):
                meta_value=[meta_value]
            for i, value in enumerate(meta_value):
                s3_header_key = 'x-archive-meta{0:02d}-{1}'.format(i, meta_key)
                encoded_header = encode_s3_header(s3_header_key, value)
                if encoded_header:
                    header_key, header_value = encoded_header
                    headers[header_key] = header_value
        except TypeError:
            s3_header_key = 'x-archive-meta-{0}'.format(meta_key)
            encoded_header = encode_s3_header(s3_header_key, value)
            if encoded_header:
                header_key, header_value = encoded_header
                headers[header_key] = header_value
    return headers
