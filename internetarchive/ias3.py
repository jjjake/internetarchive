import json

from . import __version__, config



# get_headers()
#_________________________________________________________________________________________
def build_headers(metadata={}, headers={}, auto_make_bucket=True, **kwargs):
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
    headers['Authorization'] = 'LOW {0}:{1}'.format(access_key, secret_key)
    if auto_make_bucket:
        headers['x-archive-auto-make-bucket'] = 1
    scanner = 'Internet Archive Python library {0}'.format(__version__)
    headers['x-archive-meta-scanner'] = scanner
    if not kwargs.get('queue_derive', True):
        headers['x-archive-queue-derive'] = 0

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
