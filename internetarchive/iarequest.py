#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2026 Internet Archive
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

:copyright: (C) 2012-2025 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
import copy
import logging
import re
from urllib.parse import quote

import requests
import requests.models
from jsonpatch import make_patch

from internetarchive import __version__, auth
from internetarchive.exceptions import ItemLocateError
from internetarchive.utils import delete_items_from_dict, json, needs_quote

logger = logging.getLogger(__name__)


class S3Request(requests.models.Request):
    """A Request object for IA-S3 uploads.

    Extends :class:`requests.Request` to handle Archive.org S3-like
    upload requests, including metadata headers and derive queue settings.

    :param metadata: Item-level metadata to set on upload.
    :param file_metadata: File-level metadata for the uploaded file.
    :param queue_derive: Whether to queue derivation after upload.
                        Defaults to ``True``.
    :param access_key: IA-S3 access key for authentication.
    :param secret_key: IA-S3 secret key for authentication.
    :param kwargs: Additional arguments passed to :class:`requests.Request`.
    """

    def __init__(self,
                 metadata=None,
                 file_metadata=None,
                 queue_derive=True,
                 access_key=None,
                 secret_key=None,
                 **kwargs):

        super().__init__(**kwargs)

        self.auth = self.auth or auth.S3Auth(access_key, secret_key)
        self.metadata = metadata or {}
        self.file_metadata = file_metadata or {}
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
    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, queue_derive=None,
                metadata=None, file_metadata=None):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers, metadata, file_metadata, queue_derive)
        self.prepare_cookies(cookies)
        self.prepare_body(data, files)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_headers(self, headers, metadata, file_metadata, queue_derive):
        headers = headers.copy() if headers else {}
        metadata = metadata.copy() if metadata else {}
        file_metadata = file_metadata.copy() if file_metadata else {}

        prepared_metadata = prepare_metadata(metadata)
        prepared_file_metadata = prepare_metadata(file_metadata)

        headers.setdefault('x-archive-auto-make-bucket', '1')
        headers['x-archive-queue-derive'] = '0' if queue_derive is False else '1'

        self._add_metadata_headers(headers, prepared_metadata, 'meta')
        self._add_metadata_headers(headers, prepared_file_metadata, 'filemeta')

        super().prepare_headers(headers)

    def _add_metadata_headers(self, headers, prepared_metadata, meta_type):
        for key, values in prepared_metadata.items():
            if not isinstance(values, list):
                values = [values]
            for idx, value in enumerate(values):
                if not value:
                    continue
                header_key = f'x-archive-{meta_type}{idx:02d}-{key}'.replace('_', '--')
                if isinstance(value, str) and needs_quote(value):
                    value = f'uri({quote(value)})'
                headers[header_key] = value


class MetadataRequest(requests.models.Request):
    """A Request object for metadata modifications.

    Extends :class:`requests.Request` to handle Archive.org Metadata API
    requests. Automatically generates JSON Patch operations from the
    provided metadata.

    :param metadata: Metadata dict to apply to the item.
    :param source_metadata: Current item metadata (fetched automatically if not provided).
    :param target: Metadata target (e.g., ``'metadata'``, ``'files/foo.txt'``).
    :param priority: Task priority (-10 to 10).
    :param access_key: IA-S3 access key for authentication.
    :param secret_key: IA-S3 secret key for authentication.
    :param append: Append values to existing string fields.
    :param expect: Dict of expectations for server-side validation.
    :param append_list: Append values to existing list fields.
    :param insert: Insert values at specific list indices.
    :param reduced_priority: Submit at reduced priority to avoid rate limiting.
    :param kwargs: Additional arguments passed to :class:`requests.Request`.
    """

    def __init__(self,
                 metadata=None,
                 source_metadata=None,
                 target=None,
                 priority=None,
                 access_key=None,
                 secret_key=None,
                 append=None,
                 expect=None,
                 append_list=None,
                 insert=None,
                 reduced_priority=None,
                 **kwargs):

        super().__init__(**kwargs)

        self.auth = self.auth or auth.S3PostAuth(access_key, secret_key)
        self.metadata = metadata or {}
        self.source_metadata = source_metadata
        self.target = target
        self.priority = priority
        self.append = append
        self.expect = expect or {}
        self.append_list = append_list
        self.insert = insert
        self.reduced_priority = reduced_priority

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
            expect=self.expect,
            append_list=self.append_list,
            insert=self.insert,
            reduced_priority=self.reduced_priority,
        )
        return p


class MetadataPreparedRequest(requests.models.PreparedRequest):
    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, metadata=None,
                source_metadata=None, target=None, priority=None, append=None,
                expect=None, append_list=None, insert=None, reduced_priority=None):
        # First handle our custom headers
        if reduced_priority:
            headers = headers.copy() if headers else {}
            headers['X-Accept-Reduced-Priority'] = '1'

        # Now run full parent preparation
        super().prepare(
            method=method,
            url=url,
            headers=headers,
            files=files,
            data=data,
            params=params,
            auth=auth,
            cookies=cookies,
            hooks=hooks,
        )

        # Now add our custom handling
        self.identifier = self.url.split('?')[0].split('/')[-1]
        self._prepare_request_body(
            metadata,
            source_metadata,
            target,
            priority,
            append,
            append_list,
            insert,
            expect,
        )
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def _prepare_request_body(self, metadata, source_metadata, target, priority,
                              append, append_list, insert, expect):
        if not source_metadata:
            r = requests.get(self.url, timeout=10)
            source_metadata = r.json()

        if self._is_multi_target(metadata):
            changes = self._prepare_multi_target_changes(
                metadata,
                source_metadata,
                target,
                append,
                expect,
                append_list,
                insert,
            )
            self.data = {'-changes': json.dumps(changes), 'priority': priority or -5}
        else:
            self._prepare_single_target_body(
                metadata,
                source_metadata,
                target,
                append,
                append_list,
                insert,
                expect,
                priority,
            )

        logger.debug(f'submitting metadata request: {self.data}')
        super().prepare_body(self.data, None)

    def _is_multi_target(self, metadata):
        return (
            isinstance(metadata, list)
            or any('/' in k for k in metadata)
            or all(isinstance(v, dict) for v in metadata.values())
        )

    def _prepare_multi_target_changes(self, metadata, source_metadata, target,
                                      append, expect, append_list, insert):
        changes = []
        if target:
            metadata = {target: metadata}
        for key in metadata:
            patch = self._get_patch_for_target(
                key,
                metadata[key],
                source_metadata,
                append,
                expect,
                append_list,
                insert,
            )
            changes.append({'target': key, 'patch': patch})
        return changes

    def _prepare_single_target_body(self, metadata, source_metadata, target, append,
                                    append_list, insert, expect, priority):
        target = target or 'metadata'
        if target == 'metadata':
            try:
                patch = prepare_patch(
                    metadata,
                    source_metadata['metadata'],
                    append,
                    expect,
                    append_list,
                    insert,
                )
            except KeyError:
                raise ItemLocateError(
                    f'{self.identifier} cannot be located '
                    'because it is dark or does not exist.'
                )
        elif target.startswith('files/'):
            patch = prepare_files_patch(
                metadata,
                source_metadata['files'],
                target,
                append,
                append_list,
                insert,
                expect,
            )
        else:
            patch = prepare_target_patch(
                metadata,
                source_metadata,
                append,
                target,
                append_list,
                insert,
                expect,
            )
        self.data = {
            '-patch': json.dumps(patch),
            '-target': target,
            'priority': priority or -5,
        }


def prepare_patch(metadata, source_metadata, append, expect=None,
                  append_list=None, insert=None):
    """Create a JSON Patch from metadata changes.

    :param metadata: New metadata to apply (dict or list).
    :param source_metadata: Current metadata from the item.
    :param append: If ``True``, append string values to existing values.
    :param expect: Dict of expectations for server-side validation.
    :param append_list: If ``True``, append to existing list values.
    :param insert: If ``True``, insert at specific list indices.
    :returns: A list of JSON Patch operations.
    """
    destination = source_metadata.copy()
    if isinstance(metadata, list):
        prepared_metadata = metadata
        if not destination:
            destination = []
    else:
        prepared_metadata = prepare_metadata(
            metadata,
            source_metadata,
            append,
            append_list,
            insert,
        )
    if isinstance(destination, dict):
        destination.update(prepared_metadata)
    elif isinstance(metadata, list):
        destination = prepared_metadata
    else:
        if isinstance(prepared_metadata, list):
            destination = prepared_metadata
        else:
            destination = [prepared_metadata]

    destination = delete_items_from_dict(destination, 'REMOVE_TAG')
    patch = make_patch(source_metadata, destination).patch
    patch_tests = _create_patch_tests(expect)
    return patch_tests + patch


def _create_patch_tests(expect):
    tests = []
    for key, value in (expect or {}).items():
        if '[' in key:
            parts = key.split('[')
            idx = int(parts[1].strip(']'))
            path = f'/{parts[0]}/{idx}'
        else:
            path = f'/{key}'
        tests.append({'op': 'test', 'path': path, 'value': value})
    return tests


def prepare_target_patch(metadata, source_metadata, append, target,
                         append_list, insert, expect):
    """Create a JSON Patch for a specific metadata target path.

    :param metadata: New metadata to apply.
    :param source_metadata: Current metadata from the item.
    :param append: If ``True``, append string values to existing values.
    :param target: The metadata target path (e.g., ``'metadata/collection'``).
    :param append_list: If ``True``, append to existing list values.
    :param insert: If ``True``, insert at specific list indices.
    :param expect: Dict of expectations for server-side validation.
    :returns: A list of JSON Patch operations.
    """
    def get_nested_value(data, parts):
        current = data
        for part in parts:
            if isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                current = current[part]
        return current

    key_parts = target.split('/')
    current_source = get_nested_value(source_metadata, key_parts)

    return prepare_patch(
        metadata,
        current_source,
        append,
        expect,
        append_list,
        insert,
    )


def prepare_files_patch(metadata, files_metadata, target, append,
                        append_list, insert, expect):
    """Create a JSON Patch for file-level metadata.

    :param metadata: New metadata to apply to the file.
    :param files_metadata: List of file metadata dicts from the item.
    :param target: The target path (e.g., ``'files/foo.txt'``).
    :param append: If ``True``, append string values to existing values.
    :param append_list: If ``True``, append to existing list values.
    :param insert: If ``True``, insert at specific list indices.
    :param expect: Dict of expectations for server-side validation.
    :returns: A list of JSON Patch operations, or empty list if file not found.
    """
    filename = target.split('/')[1]
    for file_meta in files_metadata:
        if file_meta.get('name') == filename:
            return prepare_patch(
                metadata,
                file_meta,
                append,
                expect,
                append_list,
                insert,
            )
    return []


def prepare_metadata(metadata, source_metadata=None, append=False,
                     append_list=False, insert=False):
    """Normalize and merge metadata before building JSON Patch.

    Handles both plain key/value metadata and "indexed" keys like
    ``subject[0]``, ``subject[1]``, etc. that represent list elements.

    :param metadata: New metadata to apply.
    :param source_metadata: Existing metadata from the item.
    :param append: If ``True``, append values for existing keys (concatenate strings).
    :param append_list: If ``True``, append values to lists.
    :param insert: If ``True``, insert elements instead of overwriting.
    :returns: Prepared metadata dictionary ready for patch generation.
    """
    # Deep copy source to avoid mutating input
    source = copy.deepcopy(source_metadata) if source_metadata else {}
    prepared = {}

    # If using insert-mode but metadata has no indexed keys,
    # rewrite unindexed keys as [0]-indexed to normalize.
    if insert and not all(_is_indexed_key(k) for k in metadata):
        for k in list(metadata):
            if not _is_indexed_key(k):
                metadata[f"{k}[0]"] = metadata[k]

    _process_non_indexed_keys(metadata, source, prepared, append, append_list)
    indexed_keys = _process_indexed_keys(metadata, source, prepared, insert)

    return prepared


def _process_non_indexed_keys(metadata, source, prepared, append, append_list):
    """
    Process plain (non-indexed) metadata keys.

    Handles:
      - Numeric value conversion to strings.
      - String concatenation when `append` is True.
      - List extension when `append_list` is True.
    """
    for key, value in metadata.items():
        # Skip indexed keys; handled in _process_indexed_keys().
        if _is_indexed_key(key):
            continue

        current_key = key

        if append_list and isinstance(source, dict) and source.get(current_key):
            existing = source[current_key]
            if not isinstance(existing, list):
                existing = [existing]
            prepared[current_key] = existing + [value]
        elif append and source.get(current_key):
            if isinstance(source[current_key], list):
                raise ValueError(
                    "Cannot append to list metadata with 'append' flag; "
                    "use 'append_list' instead.")
            prepared[current_key] = f'{source[current_key]} {value}'
        else:
            prepared[current_key] = value


def _process_indexed_keys(metadata, source, prepared, insert):
    """Process indexed metadata keys such as ``subject[0]``, ``subject[1]``, etc.

    Builds list values in ``prepared`` based on these indexed keys.
    Merges with any existing list data from ``source``, optionally
    inserting new values when ``insert=True`` (otherwise existing values
    are overwritten at the given index).

    Also filters out ``None`` and ``'REMOVE_TAG'`` placeholders, which
    indicate that a list element should be deleted.

    :param metadata: Input metadata possibly containing indexed keys.
    :param source: Existing metadata for the item.
    :param prepared: Dict being built up by :func:`prepare_metadata`.
    :param insert: If ``True``, insert elements instead of overwriting.
    :returns: Mapping of base keys to original list lengths (for reference).
    """
    indexed_keys = {}
    # Track explicit indexes to delete (where value is REMOVE_TAG)
    remove_indexes = {}

    for key in list(metadata.keys()):
        # Skip non-indexed keys; handled in _process_non_indexed_keys().
        if not _is_indexed_key(key):
            continue

        # Extract base key ('subject' from 'subject[2]')
        base = _get_base_key(key)
        # Extract list index (2 from 'subject[2]')
        idx = _get_index(key)

        if base not in indexed_keys:
            # Initialize this base key once per group of indexed keys.
            # Pull any existing list data from the source metadata.
            source_list = source.get(base, [])
            if not isinstance(source_list, list):
                source_list = [source_list]

            indexed_keys[base] = len(source_list)

            # Preallocate enough None slots to handle incoming indices.
            current_metadata_length = len(metadata)
            prepared[base] = source_list + [None] * (
                current_metadata_length - len(source_list)
            )

        # Ensure we're working with a list at this point.
        if not isinstance(prepared[base], list):
            prepared[base] = [prepared[base]]

        # Make sure list is long enough to hold this index.
        while len(prepared[base]) <= idx:
            prepared[base].append(None)

        # Track REMOVE_TAG for later deletion
        if metadata[key] == 'REMOVE_TAG':
            remove_indexes.setdefault(base, []).append(idx)
            prepared[base][idx] = None  # Placeholder for now
        elif insert:
            # In "insert" mode, insert at index (shift others right),
            # and remove duplicates if value already exists.
            if metadata[key] in prepared[base]:
                prepared[base].remove(metadata[key])
            prepared[base].insert(idx, metadata[key])
        else:
            # Default mode: overwrite value at given index.
            prepared[base][idx] = metadata[key]

    # Cleanup lists: first remove explicit REMOVE_TAG indexes
    for base, indexes in remove_indexes.items():
        for idx in sorted(indexes, reverse=True):
            if idx < len(prepared[base]):
                del prepared[base][idx]

    # Then remove any remaining None values from preallocation
    for base in prepared:
        if isinstance(prepared[base], list):
            prepared[base] = [v for v in prepared[base] if v is not None]

    return indexed_keys


def _get_base_key(key):
    """Return the part of a metadata key before any [index] notation."""
    return key.split('[')[0]


def _is_indexed_key(key):
    """Return True if key includes [n] list indexing syntax."""
    return '[' in key and ']' in key


def _get_index(key):
    """Extract integer index from an indexed metadata key (e.g. 'subject[2]')."""
    match = re.search(r'(?<=\[)\d+(?=\])', key)
    return int(match.group()) if match else None
