# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2017 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.iarequest
~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2017 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

try:
    import ujson as json
except ImportError:
    import json
import re
import copy

from six.moves import urllib
import requests.models
import requests
from jsonpatch import make_patch
import six

from internetarchive import auth, __version__
from internetarchive.utils import needs_quote


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

    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, queue_derive=None,
                metadata={}):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers, metadata, queue_derive)
        self.prepare_cookies(cookies)
        self.prepare_body(data, files)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_headers(self, headers, metadata, queue_derive=True):
        """Convert a dictionary of metadata into S3 compatible HTTP
        headers, and append headers to ``headers``.

        :type metadata: dict
        :param metadata: Metadata to be converted into S3 HTTP Headers
                         and appended to ``headers``.

        :type headers: dict
        :param headers: (optional) S3 compatible HTTP headers.

        """
        if not metadata.get('scanner'):
            scanner = 'Internet Archive Python library {0}'.format(__version__)
            metadata['scanner'] = scanner
        prepared_metadata = prepare_metadata(metadata)

        headers['x-archive-auto-make-bucket'] = '1'
        if queue_derive is False:
            headers['x-archive-queue-derive'] = '0'
        else:
            headers['x-archive-queue-derive'] = '1'

        for meta_key, meta_value in prepared_metadata.items():
            # Encode arrays into JSON strings because Archive.org does not
            # yet support complex metadata structures in
            # <identifier>_meta.xml.
            if isinstance(meta_value, dict):
                meta_value = json.dumps(meta_value)
            # Convert the metadata value into a list if it is not already
            # iterable.
            if (isinstance(meta_value, six.string_types) or
                    not hasattr(meta_value, '__iter__')):
                meta_value = [meta_value]
            # Convert metadata items into HTTP headers and add to
            # ``headers`` dict.
            for i, value in enumerate(meta_value):
                if not value:
                    continue
                header_key = 'x-archive-meta{0:02d}-{1}'.format(i, meta_key)
                if (isinstance(value, six.string_types) and needs_quote(value)):
                    if six.PY2 and isinstance(value, six.text_type):
                        value = value.encode('utf-8')
                    value = 'uri({0})'.format(urllib.parse.quote(value))
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
                 append=None,
                 **kwargs):

        super(MetadataRequest, self).__init__(**kwargs)

        if not self.auth:
            self.auth = auth.S3PostAuth(access_key, secret_key)
        metadata = {} if not metadata else metadata

        self.metadata = metadata
        self.source_metadata = source_metadata
        self.target = target
        self.priority = priority
        self.append = append

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
            append=self.append,
        )
        return p


class MetadataPreparedRequest(requests.models.PreparedRequest):

    # __init__()
    def __init__(self):
        super(MetadataPreparedRequest, self).__init__()

    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, metadata={},
                source_metadata=None, target=None, priority=None, append=None):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers)
        self.prepare_cookies(cookies)
        self.prepare_body(metadata, source_metadata, target, priority, append)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_body(self, metadata, source_metadata, target, priority, append):
        priority = -5 if not priority else priority

        if not source_metadata:
            r = requests.get(self.url)
            source_metadata = r.json().get(target.split('/')[0], {})
        if 'metadata' in target:
            destination_metadata = source_metadata.copy()
            prepared_metadata = prepare_metadata(metadata, source_metadata, append)
            destination_metadata.update(prepared_metadata)
        elif 'files' in target:
            filename = '/'.join(target.split('/')[1:])
            for f in source_metadata:
                if f.get('name') == filename:
                    source_metadata = f
                    break
            destination_metadata = source_metadata.copy()
            prepared_metadata = prepare_metadata(metadata, source_metadata, append)
            destination_metadata.update(prepared_metadata)
        else:
            destination_metadata = source_metadata.copy()
            prepared_metadata = prepare_metadata(metadata, source_metadata, append)
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
    """Prepare a metadata dict for an
    :class:`S3PreparedRequest <S3PreparedRequest>` or
    :class:`MetadataPreparedRequest <MetadataPreparedRequest>` object.

    :type metadata: dict
    :param metadata: The metadata dict to be prepared.

    :type source_metadata: dict
    :param source_metadata: (optional) The source metadata for the item
                            being modified.

    :rtype: dict
    :returns: A filtered metadata dict to be used for generating IA
              S3 and Metadata API requests.

    """
    # Make a deepcopy of source_metadata if it exists. A deepcopy is
    # necessary to avoid modifying the original dict.
    source_metadata = {} if not source_metadata else copy.deepcopy(source_metadata)
    prepared_metadata = {}

    # Functions for dealing with metadata keys containing indexes.
    def get_index(key):
        match = re.search(r'(?<=\[)\d+(?=\])', key)
        if match is not None:
            return int(match.group())

    def rm_index(key):
        return key.split('[')[0]

    # Create indexed_keys counter dict. i.e.: {'subject': 3} -- subject
    # (with the index removed) appears 3 times in the metadata dict.
    indexed_keys = {}
    for key in metadata:
        # Convert number values to strings!
        if isinstance(metadata[key], (six.integer_types, float, complex)):
            metadata[key] = str(metadata[key])
        if get_index(key) is None:
            continue
        count = len([x for x in metadata if rm_index(x) == rm_index(key)])
        indexed_keys[rm_index(key)] = count

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
        # Insert values from indexed keys into prepared_metadata dict.
        if (rm_index(key) in indexed_keys):
            try:
                prepared_metadata[rm_index(key)][get_index(key)] = metadata[key]
            except IndexError:
                prepared_metadata[rm_index(key)].append(metadata[key])
        # If append is True, append value to source_metadata value.
        elif append and source_metadata.get(key):
            prepared_metadata[key] = '{0} {1}'.format(
                source_metadata[key].encode('utf-8'), metadata[key])
        else:
            prepared_metadata[key] = metadata[key]

    # Remove values from metadata if value is REMOVE_TAG.
    _done = []
    for key in indexed_keys:
        # Filter None values from items with arrays as values
        prepared_metadata[key] = [v for v in prepared_metadata[key] if v]
        # Only filter the given indexed key if it has not already been
        # filtered.
        if key not in _done:
            indexes = []
            for k in metadata:
                if not get_index(k):
                    continue
                elif not rm_index(k) == key:
                    continue
                elif not metadata[k] == 'REMOVE_TAG':
                    continue
                else:
                    indexes.append(get_index(k))
            # Delete indexed values in reverse to not throw off the
            # subsequent indexes.
            for i in sorted(indexes, reverse=True):
                del prepared_metadata[key][i]
            _done.append(key)

    return prepared_metadata
