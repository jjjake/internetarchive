# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2019 Internet Archive
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

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import

try:
    import ujson as json
except ImportError:
    import json
import re
import copy
import logging

from six.moves import urllib
import requests.models
import requests
from jsonpatch import make_patch
import six

from internetarchive import auth, __version__
from internetarchive.utils import needs_quote, delete_items_from_dict
from internetarchive.exceptions import ItemLocateError


logger = logging.getLogger(__name__)


class S3Request(requests.models.Request):
    def __init__(self,
                 metadata=None,
                 file_metadata=None,
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
        self.file_metadata = file_metadata
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
            file_metadata=self.file_metadata,
            queue_derive=self.queue_derive,
        )
        return p


class S3PreparedRequest(requests.models.PreparedRequest):

    # __init__()
    def __init__(self):
        super(S3PreparedRequest, self).__init__()

    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, queue_derive=None,
                metadata=None, file_metadata=None):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers, metadata,
                             file_metadata=file_metadata,
                             queue_derive=queue_derive)
        self.prepare_cookies(cookies)
        self.prepare_body(data, files)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_headers(self, headers, metadata, file_metadata=None, queue_derive=True):
        """Convert a dictionary of metadata into S3 compatible HTTP
        headers, and append headers to ``headers``.

        :type metadata: dict
        :param metadata: Metadata to be converted into S3 HTTP Headers
                         and appended to ``headers``.

        :type headers: dict
        :param headers: (optional) S3 compatible HTTP headers.

        """
        metadata = dict() if metadata is None else metadata
        file_metadata = dict() if file_metadata is None else file_metadata

        if not metadata.get('scanner'):
            scanner = 'Internet Archive Python library {0}'.format(__version__)
            metadata['scanner'] = scanner
        prepared_metadata = prepare_metadata(metadata)
        prepared_file_metadata = prepare_metadata(file_metadata)

        headers['x-archive-auto-make-bucket'] = '1'
        if 'x-archive-queue-derive' not in headers:
            if queue_derive is False:
                headers['x-archive-queue-derive'] = '0'
            else:
                headers['x-archive-queue-derive'] = '1'

        def _prepare_metadata_headers(prepared_metadata, meta_type='meta'):
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
                    header_key = 'x-archive-{0}{1:02d}-{2}'.format(meta_type, i, meta_key)
                    if (isinstance(value, six.string_types) and needs_quote(value)):
                        if six.PY2 and isinstance(value, six.text_type):
                            value = value.encode('utf-8')
                        value = 'uri({0})'.format(urllib.parse.quote(value))
                    # because rfc822 http headers disallow _ in names, IA-S3 will
                    # translate two hyphens in a row (--) into an underscore (_).
                    header_key = header_key.replace('_', '--')
                    headers[header_key] = value

        # Parse the prepared metadata into HTTP headers,
        # and add them to the ``headers`` dict.
        _prepare_metadata_headers(prepared_metadata)
        _prepare_metadata_headers(prepared_file_metadata, meta_type='filemeta')

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
                 append_list=None,
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
        self.append_list = append_list

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
            append_list=self.append_list,
        )
        return p


class MetadataPreparedRequest(requests.models.PreparedRequest):

    # __init__()
    def __init__(self):
        super(MetadataPreparedRequest, self).__init__()

    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, metadata={},
                source_metadata=None, target=None, priority=None, append=None,
                append_list=None):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers)
        self.prepare_cookies(cookies)
        self.prepare_body(metadata, source_metadata, target, priority, append,
                          append_list)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_body(self, metadata, source_metadata, target, priority, append,
                     append_list):
        priority = -5 if not priority else priority

        if not source_metadata:
            r = requests.get(self.url)
            source_metadata = r.json()

        # Write to many targets
        if isinstance(metadata, list) \
                or any('/' in k for k in metadata) \
                or all(isinstance(k, dict) for k in metadata.values()):
            changes = list()

            if any(not k for k in metadata):
                raise ValueError('Invalid metadata provided, '
                                 'check your input and try again')

            if target:
                metadata = {target: metadata}
            for key in metadata:
                if key == 'metadata':
                    try:
                        patch = prepare_patch(metadata[key],
                                              source_metadata['metadata'],
                                              append,
                                              append_list)
                    except KeyError:
                        raise ItemLocateError
                elif key.startswith('files'):
                    patch = prepare_files_patch(metadata[key],
                                                source_metadata['files'],
                                                append,
                                                key,
                                                append_list)
                else:
                    key = key.split('/')[0]
                    patch = prepare_target_patch(metadata, source_metadata, append,
                                                 target, append_list, key)
                changes.append({'target': key, 'patch': patch})
            self.data = {
                '-changes': json.dumps(changes),
                'priority': priority,
            }
            logger.debug('submitting metadata request: {}'.format(self.data))
        # Write to single target
        else:
            if not target or 'metadata' in target:
                target = 'metadata'
                try:
                    patch = prepare_patch(metadata, source_metadata['metadata'], append,
                                          append_list)
                except KeyError:
                    raise ItemLocateError
            elif 'files' in target:
                patch = prepare_files_patch(metadata, source_metadata['files'], append,
                                            target, append_list)
            else:
                metadata = {target: metadata}
                patch = prepare_target_patch(metadata, source_metadata, append,
                                             target, append_list, target)
            self.data = {
                '-patch': json.dumps(patch),
                '-target': target,
                'priority': priority,
            }
            logger.debug('submitting metadata request: {}'.format(self.data))
        super(MetadataPreparedRequest, self).prepare_body(self.data, None)


def prepare_patch(metadata, source_metadata, append, append_list=None):
    destination_metadata = source_metadata.copy()
    if isinstance(metadata, list):
        prepared_metadata = metadata
        if not destination_metadata:
            destination_metadata = list()
    else:
        prepared_metadata = prepare_metadata(metadata, source_metadata, append,
                                             append_list)
    if isinstance(destination_metadata, dict):
        destination_metadata.update(prepared_metadata)
    elif isinstance(metadata, list) and not destination_metadata:
        destination_metadata = metadata
    else:
        if isinstance(prepared_metadata, list):
            if append_list:
                destination_metadata += prepared_metadata
            else:
                destination_metadata = prepared_metadata
        else:
            destination_metadata.append(prepared_metadata)
    # Delete metadata items where value is REMOVE_TAG.
    destination_metadata = delete_items_from_dict(destination_metadata, 'REMOVE_TAG')
    patch = make_patch(source_metadata, destination_metadata).patch
    return patch


def prepare_target_patch(metadata, source_metadata, append, target, append_list, key):

    def dictify(lst, key=None, value=None):
        if not lst:
            return value
        sub_dict = dictify(lst[1:], key, value)
        for i, v in enumerate(lst):
            md = {v: copy.deepcopy(sub_dict)}
            return md

    for _k in metadata:
        metadata = dictify(_k.split('/')[1:], _k.split('/')[-1], metadata[_k])
    for i, _k in enumerate(key.split('/')):
        if i == 0:
            source_metadata = source_metadata.get(_k, dict())
        else:
            source_metadata[_k] = source_metadata.get(_k, dict()).get(_k, dict())
    patch = prepare_patch(metadata, source_metadata, append, append_list)
    return patch


def prepare_files_patch(metadata, source_metadata, append, target, append_list):
    filename = '/'.join(target.split('/')[1:])
    for f in source_metadata:
        if f.get('name') == filename:
            source_metadata = f
            break
    patch = prepare_patch(metadata, source_metadata, append, append_list)
    return patch


def prepare_metadata(metadata, source_metadata=None, append=False, append_list=False):
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
        elif append_list and source_metadata.get(key):
            if not isinstance(metadata[key], list):
                metadata[key] = [metadata[key]]
            for v in metadata[key]:
                if not isinstance(source_metadata[key], list):
                    if v in [source_metadata[key]]:
                        continue
                else:
                    if v in source_metadata[key]:
                        continue
                if not isinstance(source_metadata[key], list):
                    prepared_metadata[key] = [source_metadata[key]]
                else:
                    prepared_metadata[key] = source_metadata[key]
                prepared_metadata[key].append(v)
        elif append and source_metadata.get(key):
            prepared_metadata[key] = '{0} {1}'.format(
                source_metadata[key], metadata[key])
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
