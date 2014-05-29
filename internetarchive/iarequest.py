import json
import re
import copy
import sys
# py26 support...
if sys.version_info < (2, 7):
    from counter import Counter
else:
    from collections import Counter

import requests.models
import requests
from jsonpatch import make_patch

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
        prepared_metadata = prepare_metadata(metadata)
        headers['x-archive-auto-make-bucket'] = 1
        for meta_key, meta_value in prepared_metadata.items():
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
        metadata=None,
        source_metadata=None,
        target=None,
        priority=None,
        access_key=None,
        secret_key=None,
        **kwargs):

        super(MetadataRequest, self).__init__(**kwargs)

        if not self.auth:
            self.auth = auth.MetadataAuth(access_key, secret_key)
        metadata = {} if not metadata else metadata

        self.metadata = metadata
        self.source_metadata = source_metadata
        self.target = target
        self.priority = priority

    def prepare(self):
        p = MetadataPreparedRequest()
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

            # MetadataRequest kwargs.
            metadata=self.metadata,
            priority=self.priority,
            source_metadata=self.source_metadata,
            target=self.target,
        )
        return p


class MetadataPreparedRequest(requests.models.PreparedRequest):

    # __init__()
    def __init__(self):
        super(MetadataPreparedRequest, self).__init__()

    # prepare()
    #_____________________________________________________________________________________
    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, metadata={},
                source_metadata=None, target=None, priority=None):

        method = 'POST' if not method else method

        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers)
        self.prepare_cookies(cookies)
        self.prepare_body(metadata, source_metadata, target, priority)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_body(self, metadata, source_metadata, target, priority):
        target = 'metadata' if not target else target
        priority = 0 if not priority else priority

        if not source_metadata:
            r = requests.get(self.url)
            source_metadata = r.json().get(target, {})
        destination_metadata = source_metadata.copy()
        prepared_metadata = prepare_metadata(metadata, source_metadata)
        destination_metadata.update(prepared_metadata)

        # Delete metadata items where value is REMOVE_TAG.
        destination_metadata = dict(
            (k, v) for (k, v) in destination_metadata.items() if v != 'REMOVE_TAG'
        )

        patch = json.dumps(make_patch(source_metadata, destination_metadata).patch)

        self.data = {
            '-patch': patch,
            '-target': target,
            'priority': priority,
        }

        super(MetadataPreparedRequest, self).prepare_body(self.data, None)


def prepare_metadata(metadata, source_metadata=None, append=False):
    # Make a deepcopy of source_metadata if it exists. A deepcopy is
    # necessary to avoid modifying the original dict.
    source_metadata = {} if not source_metadata else copy.deepcopy(source_metadata)
    prepared_metadata = {}

    contains_index = lambda k: re.search(r'\[\d+\]', k)
    get_index = lambda k: int(re.search(r'(?<=\[)\d+(?=\])', k).group())
    rm_index = lambda k: k.split('[')[0]
    # Create indexed_keys counter dict. i.e.: {'subject': 3} -- subject
    # (with the index removed) appears in 3 times in the metadata dict.
    indexed_keys = Counter([rm_index(k) for k in metadata if contains_index(k)])

    # Initialize the values for all indexed_keys.
    for key in indexed_keys:
        # Increment the counter so we know how many values the final 
        # value in prepared_metadata should have.
        indexed_keys[key] += len(source_metadata.get(key, []))
        # Intialize the value in the prepared_metadata dict.
        prepared_metadata[key] = source_metadata.get(key, [])
        if not isinstance(prepared_metadata[key], list):
            prepared_metadata[key] = [prepared_metadata[key]]
        # Fill the value of the prepared_metadata key with None values
        # so all indexed items can be indexed in order.
        while len(prepared_metadata[key]) < indexed_keys[key]:
            prepared_metadata[key].append(None)

    # Index all items which contain an index.
    for key in metadata:
        if (rm_index(key) in indexed_keys):
            if metadata[key] in source_metadata.get(rm_index(key), ''):
                continue
            prepared_metadata[rm_index(key)].insert(get_index(key), metadata[key])
        elif append:
            prepared_metadata[key] = '{0} {1}'.format(source_metadata[key], metadata[key])
        else:
            prepared_metadata[key] = metadata[key]

    # Filter out None values.
    for key in indexed_keys:
        prepared_metadata[key] = [v for v in prepared_metadata[key] if v]

    return prepared_metadata
