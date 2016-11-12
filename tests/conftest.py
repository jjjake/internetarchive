from __future__ import absolute_import

import json
import os
from subprocess import Popen, PIPE

import pytest
import responses
from responses import RequestsMock

from internetarchive import get_session
from internetarchive.api import get_item

PROTOCOL = 'https:'
BASE_URL = 'https://archive.org/'
METADATA_URL = BASE_URL + 'metadata/'
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NASA_METADATA_PATH = os.path.join(ROOT_DIR, 'tests/data/metadata/nasa.json')


def load_file(filename):
    with open(filename, 'r') as fh:
        return fh.read()


def load_test_data_file(filename):
    return load_file(os.path.join(ROOT_DIR, 'tests/data/', filename))


def call_cmd(cmd):
    proc = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    return (proc.returncode, stdout, stderr)


class IaRequestsMock(RequestsMock):
    def add_metadata_mock(self, identifier, body=None, method=responses.GET):
        url = METADATA_URL + identifier
        if body is None:
            body = load_test_data_file('metadata/' + identifier + '.json')
        self.add(method, url, body=body, content_type='application/json')


@pytest.fixture
def nasa_mocker():
    with IaRequestsMock() as mocker:
        mocker.add_metadata_mock('nasa')
        yield mocker


@pytest.fixture
def nasa_item():
    session = get_session()
    with IaRequestsMock() as mocker:
        mocker.add_metadata_mock('nasa')
        yield session.get_item('nasa')


@pytest.fixture
def session():
    return get_session()


@pytest.fixture
def nasa_metadata():
    return json.loads(load_test_data_file('metadata/nasa.json'))


@pytest.fixture
def nasa_item(nasa_mocker):
    return get_item('nasa')
