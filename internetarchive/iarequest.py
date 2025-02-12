#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
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
    def __init__(self,
                 metadata=None,
                 file_metadata=None,
                 queue_derive=True,
                 access_key=None,
                 secret_key=None,
                 set_scanner=True,
                 **kwargs):

        super().__init__(**kwargs)

        self.auth = self.auth or auth.S3Auth(access_key, secret_key)
        self.metadata = metadata or {}
        self.file_metadata = file_metadata or {}
        self.queue_derive = queue_derive
        self.set_scanner = set_scanner

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
            set_scanner=self.set_scanner,
        )
        return p


class S3PreparedRequest(requests.models.PreparedRequest):
    def prepare(self, method=None, url=None, headers=None, files=None, data=None,
                params=None, auth=None, cookies=None, hooks=None, queue_derive=None,
                metadata=None, file_metadata=None, set_scanner=None):
        self.prepare_method(method)
        self.prepare_url(url, params)
        self.prepare_headers(headers, metadata, file_metadata, queue_derive, set_scanner)
        self.prepare_cookies(cookies)
        self.prepare_body(data, files)
        self.prepare_auth(auth, url)
        # Note that prepare_auth must be last to enable authentication schemes
        # such as OAuth to work on a fully prepared request.

        # This MUST go after prepare_auth. Authenticators could add a hook
        self.prepare_hooks(hooks)

    def prepare_headers(self, headers, metadata, file_metadata, queue_derive,
                        set_scanner):
        headers = headers.copy() if headers else {}
        metadata = metadata.copy() if metadata else {}
        file_metadata = file_metadata.copy() if file_metadata else {}

        if set_scanner:
            scanner_value = f'Internet Archive Python library {__version__}'
            existing_scanner = metadata.get('scanner', [])
            if not isinstance(existing_scanner, list):
                existing_scanner = [existing_scanner]
            existing_scanner.append(scanner_value)
            metadata['scanner'] = existing_scanner
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
                {target: metadata},
                source_metadata,
                append,
                target,
                append_list,
                target,
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
        destination = prepared_metadata if not destination else prepared_metadata
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
                         append_list, key, insert, expect):
    nested_dict = _create_nested_dict(metadata)
    current = source_metadata
    for part in key.split('/'):
        current = current.get(part, {})
    patch = prepare_patch(nested_dict, current, append, expect, append_list, insert)
    return patch


def _create_nested_dict(metadata):
    nested = {}
    for key_path, value in metadata.items():
        parts = key_path.split('/')
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return nested


def prepare_files_patch(metadata, files_metadata, target, append,
                        append_list, insert, expect):
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
    source = copy.deepcopy(source_metadata) if source_metadata else {}
    prepared = {}

    indexed_keys = _process_indexed_keys(metadata, source, prepared)
    _process_non_indexed_keys(metadata, source, prepared, append, append_list, insert)
    _cleanup_indexed_keys(prepared, indexed_keys, metadata)

    return prepared


def _process_non_indexed_keys(metadata, source, prepared, append, append_list, insert):
    for key, value in metadata.items():
        current_key = key

        if isinstance(value, (int, float, complex)) and not isinstance(value, bool):
            value = str(value)

        if append_list and source.get(current_key):
            existing = source[current_key]
            if not isinstance(existing, list):
                existing = [existing]
            prepared[current_key] = existing + [value]
        elif append and source.get(current_key):
            prepared[current_key] = f'{source[current_key]} {value}'
        elif insert and source.get(current_key):
            existing = source[current_key]
            if not isinstance(existing, list):
                existing = [existing]
            existing.insert(0, value)
            prepared[current_key] = [v for v in existing if v]
        else:
            prepared[current_key] = value


def _cleanup_indexed_keys(prepared, indexed_keys, metadata):
    for base in indexed_keys:
        if base in prepared:
            prepared[base] = [v for v in prepared[base] if v is not None]
            indexes = [
                i for i, k in enumerate(metadata)
                if _get_base_key(k) == base and metadata[k] == 'REMOVE_TAG'
            ]
            for i in reversed(indexes):
                if i < len(prepared[base]):
                    del prepared[base][i]


def _process_indexed_keys(metadata, source, prepared):
    indexed_keys = {}
    for key in list(metadata.keys()):
        if _is_indexed_key(key):
            base = _get_base_key(key)
            idx = _get_index(key)

            if base not in indexed_keys:
                source_list = source.get(base, [])
                if not isinstance(source_list, list):
                    source_list = [source_list]
                indexed_keys[base] = len(source_list)

                current_metadata_length = len(metadata)
                prepared[base] = source_list + [None] * (
                    current_metadata_length - len(source_list)
                )

            while len(prepared[base]) <= idx:
                prepared[base].append(None)

            prepared[base][idx] = metadata[key]
            del metadata[key]
    return indexed_keys


def _get_base_key(key):
    return key.split('[')[0]


def _is_indexed_key(key):
    return '[' in key and ']' in key


def _get_index(key):
    match = re.search(r'(?<=\[)\d+(?=\])', key)
    return int(match.group()) if match else None
