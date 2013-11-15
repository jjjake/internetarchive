import json

from requests.auth import AuthBase
from requests.adapters import HTTPAdapter

from . import config



class BasicAuth(AuthBase):
    """Attaches S3 Basic Authentication to the given Request object."""
    def __init__(self, access_key=None, secret_key=None):
        if not access_key or not secret_key:
            access_key, secret_key = config.get_s3_keys()
        self.access_key = access_key
        self.secret_key = secret_key

    def __call__(self, r):
        r.headers['Authorization'] = 'LOW {0}:{1}'.format(self.access_key, 
                                                          self.secret_key)
        return r

class S3Adapter(HTTPAdapter):
    def __init__(self):
        super(S3AuthAdapter, self).__init__()



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

    # Convert kwargs into S3 Headers.
    for key, value in kwargs.items():
        if key in ['metadata', 'headers']:
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
