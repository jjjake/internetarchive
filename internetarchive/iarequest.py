import json

import requests.models

from . import auth


class S3Request(requests.models.Request):
    def __init__(self,
        metadata=None,
        queue_derive=True,
        access_key=None,
        secret_key=None,
        **kwargs):

        super(S3Request, self).__init__(**kwargs)

        if not self.auth:
            self.auth = auth.S3Auth(access_key, secret_key)

        # Default empty dicts for dict params.
        metadata = {} if metadata is None else metadata

        self.metadata = metadata
        self.queue_derive = queue_derive

    def prepare(self):
        p = S3PreparedRequest()
        p.prepare(
            method=self.method,
            url=self.url,
            headers=self.headers,
            files=self.files,
            data=self.data,
            params=self.params,
            auth=self.auth,
            cookies=self.cookies,
            hooks=self.hooks,

            # S3Request kwargs.
            metadata=self.metadata,
            queue_derive=self.queue_derive,
        )
        return p


class S3PreparedRequest(requests.models.PreparedRequest):

    # __init__()
    def __init__(self):
        super(S3PreparedRequest, self).__init__()

    # prepare()
    #_____________________________________________________________________________________
    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, queue_derive=None,
                metadata={}):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers, metadata)
        self.prepare_cookies(cookies)
        self.prepare_body(data, files)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    # prepare_headers()
    #_____________________________________________________________________________________
    def prepare_headers(self, headers, metadata):
        """Convert a dictionary of metadata into S3 compatible HTTP
        headers, and append headers to ``headers``.

        :type metadata: dict
        :param metadata: Metadata to be converted into S3 HTTP Headers
                         and appended to ``headers``.

        :type headers: dict
        :param headers: (optional) S3 compatible HTTP headers.

        """
        headers['x-archive-auto-make-bucket'] = 1
        for meta_key, meta_value in metadata.items():
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
                header_key = 'x-archive-meta{0:02d}-{1}'.format(i, meta_key)
                # because rfc822 http headers disallow _ in names, IA-S3 will
                # translate two hyphens in a row (--) into an underscore (_).
                header_key = header_key.replace('_', '--')
                headers[header_key] = value
        super(S3PreparedRequest, self).prepare_headers(headers)


class MetadataRequest(requests.models.Request):
    def __init__(self,
        patch=None,
        target=None,
        priority=None,
        access_key=None,
        secret_key=None,
        **kwargs):

        super(MetadataRequest, self).__init__(**kwargs)

        target = 'metadata' if not target else target
        priority = 0 if not priority else priority

        self.data = {
            '-patch': patch,
            '-target': target,
            'priority': priority,
            'access': access_key,
            'secret': secret_key,
        }
