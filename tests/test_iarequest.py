import copy
import json

import pytest

from internetarchive.iarequest import (
    MetadataRequest,
    S3Request,
    prepare_files_patch,
    prepare_patch,
    prepare_target_patch,
)
from tests.conftest import PROTOCOL, IaRequestsMock


@pytest.fixture
def sample_metadata():
    return copy.deepcopy({
        "metadata": {"title": "Test"},
        "files": [
            {"name": "test.txt", "custom": {"tags": ["old"]}, "foo": "bar"},
        ],
        "dupe_pallet_index": {
            "IA9999": ["IA999901"]
        }
    })


@pytest.mark.parametrize(("metadata", "expected"), [
    ({"custom": ["new"]}, [{'op': 'add', 'path': '/custom', 'value': ['new']}]),
    ({"title": "New Title"}, [{'op': 'replace', 'path': '/title', 'value': 'New Title'}]),
    ({"title": "REMOVE_TAG"}, [{'op': 'remove', 'path': '/title'}]),
])
def test_metadata_patch_operations(metadata, expected, sample_metadata):
    patch = prepare_patch(
        metadata=metadata,
        source_metadata=sample_metadata["metadata"],
        append=False,
        append_list=False,
        insert=False,
    )
    assert patch == expected


@pytest.mark.parametrize(("metadata", "expected"), [
    ({"new-key": ["new", "new2"]}, [{'op': 'add', 'path': '/new-key', 'value': ['new', 'new2']}]),
    ({"custom": "foo new"}, [{'op': 'replace', 'path': '/custom', 'value': 'foo new'}]),
    ({"custom": "REMOVE_TAG"}, [{'op': 'remove', 'path': '/custom'}]),
])
def test_file_metadata_patch_operations(metadata, expected, sample_metadata):
    patch = prepare_files_patch(
        metadata=metadata,
        files_metadata=sample_metadata["files"],
        target="files/test.txt",
        append=False,
        append_list=False,
        insert=False,
        expect={}
    )
    assert patch == expected


@pytest.mark.parametrize(("metadata", "expected"), [
    (
        {"IA9999": ["UPDATED"], "NEW_ITEM": ["NEW123"]},
        [
            {'op': 'add', 'path': '/NEW_ITEM', 'value': ['NEW123']},
            {'op': 'replace', 'path': '/IA9999/0', 'value': 'UPDATED'}
        ]
    ),
])
def test_target_patch_add_and_replace(metadata, expected, sample_metadata):
    patch = prepare_target_patch(
        metadata=metadata,
        source_metadata=sample_metadata,
        target="dupe_pallet_index",
        append=False,
        append_list=False,
        insert=False,
        expect={}
    )
    assert patch == expected


@pytest.mark.parametrize(("metadata", "expected"), [
    (
        {"IA9999": ["IA999901", "IA999902", "IA999903"]},
        [{'op': 'add', 'path': '/IA9999/1', 'value': ['IA999901', 'IA999902', 'IA999903']}]
    ),
    (
        {"IA9999": "IA999902"},
        [{'op': 'add', 'path': '/IA9999/1', 'value': 'IA999902'}]
    ),
])
def test_target_patch_append_list(metadata, expected, sample_metadata):
    patch = prepare_target_patch(
        metadata=metadata,
        source_metadata=sample_metadata,
        target="dupe_pallet_index",
        append=False,
        append_list=True,
        insert=False,
        expect={}
    )
    assert patch == expected


def test_metadata_request_patch_key(sample_metadata):
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock('test_item', body=json.dumps(sample_metadata))

        req = MetadataRequest(
            metadata={"title": "New Title"},
            url=f"{PROTOCOL}//archive.org/metadata/test_item"
        )
        prepared = req.prepare()
        assert any(k.endswith('-patch') for k in prepared.data)


@pytest.mark.parametrize(("test_value", "expected"), [
    (
        "http://example.com/foo bar?q=✓",
        "uri(http%3A//example.com/foo%20bar%3Fq%3D%E2%9C%93)"
    ),
])
def test_metadata_header_uri_encoding(test_value, expected):
    req = S3Request(
        method='PUT',
        url=f"{PROTOCOL}//s3.us.archive.org/test_item",
        metadata={"source": test_value},
        access_key='test_access',
        secret_key='test_secret'
    )
    prepared = req.prepare()
    header = prepared.headers.get('x-archive-meta00-source', '')
    assert header == expected
