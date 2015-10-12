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
    responses.add(responses.GET, 'http://archive.org/metadata/nasa',
                  body=testitem_metadata,
                  status=200,
                  content_type='application/json')
    return session.get_item('nasa')
