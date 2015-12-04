from __future__ import absolute_import
import os

import pytest
import responses

from internetarchive import get_session


@pytest.fixture
def json_filename():
    return os.path.join(os.path.dirname(__file__), 'data/nasa_meta.json')


@pytest.fixture
def session():
    return get_session()


@pytest.fixture
def testitem_metadata(json_filename):
    with open(json_filename, 'r') as fh:
        return fh.read().strip().decode('utf-8')


@pytest.fixture
@responses.activate
def testitem(testitem_metadata, session):
    responses.add(responses.GET, 'https://archive.org/metadata/nasa',
                  body=testitem_metadata,
                  status=200,
                  content_type='application/json')
    return session.get_item('nasa')


@pytest.fixture
def session_with_logging():
    return get_session(config={'logging': {'level': 'INFO'}})


@pytest.fixture
@responses.activate
def testitem_with_logging(testitem_metadata, session_with_logging):
    responses.add(responses.GET, 'https://archive.org/metadata/nasa',
                  body=testitem_metadata,
                  status=200,
                  content_type='application/json')
    return session_with_logging.get_item('nasa')
