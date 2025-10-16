import copy
import json

import pytest

from internetarchive.iarequest import (
    MetadataRequest,
    S3Request,
    prepare_files_patch,
    prepare_metadata,
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


@pytest.mark.parametrize(("metadata", "source", "insert", "expected"), [
    # Shift existing elements in insert mode
    ({"collection[0]": "noaa-hawaii"},
     {"collection": ["internetarchivebooks", "noaa-hawaii", "noaa", "democracys-library"]},
     True,
     {"collection": ["noaa-hawaii", "internetarchivebooks", "noaa", "democracys-library"]}),

    # Simple overwrite of an indexed key
    ({"subject[0]": "Math"},
     {"subject": "Science"},
     False,
     {"subject": ["Math"]}),

    # Indexed key overwriting existing list
    ({"subject[1]": "Science"},
     {"subject": ["Math"]},
     False,
     {"subject": ["Math", "Science"]}),

    # Insert mode: shifts existing elements
    ({"subject[1]": "History"},
     {"subject": ["Math", "Science"]},
     True,
     {"subject": ["Math", "History", "Science"]}),

    # REMOVE_TAG removes an element
    ({"subject[0]": "REMOVE_TAG"},
     {"subject": ["Math", "Science"]},
     False,
     {"subject": ["Science"]}),

    # Multiple indexed keys out of order
    ({"subject[2]": "Art", "subject[0]": "Math"},
     {},
     False,
     {"subject": ["Math", "Art"]}),

    # Insert at beginning of an existing list
    ({"subject[0]": "Physics"},
     {"subject": ["Math", "Chemistry"]},
     True,
     {"subject": ["Physics", "Math", "Chemistry"]}),

    # Insert at end of an existing list
    ({"subject[2]": "Biology"},
     {"subject": ["Math", "Chemistry"]},
     True,
     {"subject": ["Math", "Chemistry", "Biology"]}),

    # Overwrite numeric value
    ({"page[0]": 42},
     {"page": [1]},
     False,
     {"page": [42]}),

    # Mixed non-indexed and indexed keys
    ({"subject": "History", "topic[0]": "Algebra"},
     {"subject": "Math", "topic": ["English", "Geometry"]},
     False,
     {"subject": "History", "topic": ["Algebra", "Geometry"]}),

    # Remove multiple elements with REMOVE_TAG
    ({"subject[0]": "REMOVE_TAG", "subject[1]": "REMOVE_TAG"},
     {"subject": ["Math", "Science", "History"]},
     False,
     {"subject": ["History"]}),

    # Indexed key beyond current list length
    ({"subject[5]": "Philosophy"},
     {"subject": ["Math"]},
     False,
     {"subject": ["Math", "Philosophy"]}),

    # Insert mode with duplicate prevention
    ({"subject[1]": "Math"},
     {"subject": ["Math", "Science"]},
     True,
     {"subject": ["Science", "Math"]}),
])
def test_prepare_metadata_indexed_keys(metadata, source, insert, expected):
    result = prepare_metadata(metadata, source_metadata=source, insert=insert)
    # remove None placeholders for comparison
    for k, v in result.items():
        if isinstance(v, list):
            result[k] = [i for i in v if i is not None]
    assert result == expected


def test_prepare_metadata_insert_mode_and_duplicates():
    source = {"tags": ["foo", "bar"]}
    metadata = {"tags[1]": "foo"}  # duplicate value
    result = prepare_metadata(metadata, source_metadata=source, insert=True)
    # Duplicate should be removed and value inserted at index 1
    assert result["tags"] == ["bar", "foo"]


def test_prepare_metadata_with_preallocation_and_none_cleanup():
    source = {"keywords": ["python"]}
    metadata = {"keywords[3]": "testing"}
    result = prepare_metadata(metadata, source_metadata=source)
    # Index 1 and 2 are None and should be removed
    assert result["keywords"] == ["python", "testing"]


def test_prepare_metadata_numeric_conversion_and_append():
    source = {"page": 5}
    metadata = {"page": 10}
    result = prepare_metadata(metadata, source_metadata=source, append=True)
    # Numeric values should be converted to strings and concatenated
    assert result["page"] == "5 10"


def test_prepare_metadata_append_list():
    source = {"tags": ["foo"]}
    metadata = {"tags": ["bar"]}
    result = prepare_metadata(metadata, source_metadata=source, append_list=True)
    assert result["tags"] == ["foo", ["bar"]]


@pytest.mark.parametrize(("metadata", "source", "insert", "expected"), [
    # Multiple REMOVE_TAGs interleaved with inserts
    ({"tags[0]": "REMOVE_TAG", "tags[2]": "new", "tags[1]": "REMOVE_TAG"},
     {"tags": ["foo", "bar", "baz"]},
     True,
     {"tags": ["new", "baz"]}),

    # Sparse indices beyond current list length, insert mode
    ({"keywords[5]": "python", "keywords[2]": "pytest"},
     {"keywords": ["testing"]},
     True,
     {"keywords": ["testing", "pytest", "python"]}),

    # Duplicate prevention with insert mode
    ({"categories[1]": "Tech"},
     {"categories": ["Tech", "Science"]},
     True,
     {"categories": ["Science", "Tech"]}),

    # Indexed key overwrite where source is a non-list
    ({"page[0]": 99},
     {"page": 42},
     False,
     {"page": [99]}),

    # Mixed string and list in source
    ({"authors[1]": "Alice"},
     {"authors": "Bob"},
     True,
     {"authors": ["Bob", "Alice"]}),

    # REMOVE_TAG at the end of list
    ({"items[2]": "REMOVE_TAG"},
     {"items": ["A", "B", "C"]},
     False,
     {"items": ["A", "B"]}),

    # Multiple sparse inserts with duplicates
    ({"tags[0]": "python", "tags[3]": "python"},
     {"tags": ["python", "pytest"]},
     True,
     {"tags": ["pytest", "python"]}),
])
def test_prepare_metadata_edge_cases(metadata, source, insert, expected):
    result = prepare_metadata(metadata, source_metadata=source, insert=insert)
    # remove None placeholders for comparison
    for k, v in result.items():
        if isinstance(v, list):
            result[k] = [i for i in v if i is not None]
    assert result == expected
