import os
import sys
import shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
from logging import Logger

import responses

import internetarchive.session
from internetarchive import __version__


ROOT_DIR = os.getcwd()
TEST_JSON_FILE = os.path.join(ROOT_DIR, 'tests/data/nasa_meta.json')


CONFIG = {
    's3': {
        'access': 'test_access',
        'secret': 'test_secret',
    },
    'cookies': {
        'logged-in-user': 'test%40example.com',
        'logged-in-sig': 'testsig',
    },
    'logging': {
        'level': 'INFO',
        'file': 'test.log',
    },
}


def test_archive_session(tmpdir):
    tmpdir.chdir()

    s = internetarchive.session.ArchiveSession(CONFIG)
    assert os.path.isfile('test.log')

    assert CONFIG == s.config
    assert s.cookies == CONFIG['cookies']
    assert s.secure is True
    assert s.protocol == 'https:'
    assert s.access_key == 'test_access'
    assert s.secret_key == 'test_secret'
    assert s.headers['user-agent'].startswith('internetarchive/{0}'.format(__version__))


def test_get_item(tmpdir):
    tmpdir.chdir()

    with open(TEST_JSON_FILE, 'r') as fh:
        item_metadata = fh.read().strip().decode('utf-8')

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'https://archive.org/metadata/nasa',
                 body=item_metadata,
                 status=200,
                 content_type='application/json')

        s = internetarchive.session.ArchiveSession()
        item = s.get_item('nasa')
        assert item.exists is True
        assert item.identifier == 'nasa'

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'https://archive.org/metadata/nasa',
                 body=item_metadata,
                 status=400,
                 content_type='application/json')

        s = internetarchive.session.ArchiveSession(CONFIG)
        try:
            item = s.get_item('nasa')
        except Exception as exc:
            with open('test.log') as fh:
                assert '400 Client Error' in fh.read()


def test_s3_is_overloaded():
    test_body = """{
        "accesskey": "test_access",
        "bucket": "nasa",
        "detail": {
            "accesskey_ration": 74,
            "accesskey_tasks_queued": 0,
            "bucket_ration": 24,
            "bucket_tasks_queued": 0,
            "limit_reason": "",
            "rationing_engaged": 0,
            "rationing_level": 1399,
            "total_global_limit": 1799,
            "total_tasks_queued": 308
        },
        "over_limit": 0
    }"""

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'https://s3.us.archive.org',
                 body=test_body,
                 status=200,
                 content_type='application/json')
        s = internetarchive.session.ArchiveSession(CONFIG)
        r = s.s3_is_overloaded('nasa')
        assert r is False

    test_body = """{
        "accesskey": "test_access",
        "bucket": "nasa",
        "detail": {
            "accesskey_ration": 74,
            "accesskey_tasks_queued": 0,
            "bucket_ration": 24,
            "bucket_tasks_queued": 0,
            "limit_reason": "",
            "rationing_engaged": 0,
            "rationing_level": 1399,
            "total_global_limit": 1799,
            "total_tasks_queued": 308
        },
        "over_limit": 1
    }"""

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, 'https://s3.us.archive.org',
                 body=test_body,
                 status=200,
                 content_type='application/json')
        s = internetarchive.session.ArchiveSession(CONFIG)
        r = s.s3_is_overloaded('nasa')
        assert r is True
