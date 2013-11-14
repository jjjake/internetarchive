# -*- coding: utf-8 -*-
import os, sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import internetarchive

def test_build_headers():

    metadata = {
            'collection': 'test_collection',
            'foo': u'தமிழ்',
            'subject': ['foo', 'bar', 'baz'],
            'bar': 13,
            'boo': {'test': 'dict'},
            'none': None,
            'none2': False,
            'test_foo': 'underscore',
    }
    headers = {
            'x-archive-size-hint': 19327352832,
            'x-archive-test-header': 'test value',
    }

    ias3_headers = internetarchive.ias3.build_headers(metadata, headers)

    test_output = {
            # str test.
            'x-archive-meta00-collection': 'test_collection',

            # unicode test.
            'x-archive-meta00-foo': '\xe0\xae\xa4\xe0\xae\xae\xe0\xae\xbf\xe0\xae\xb4\xe0\xaf\x8d',

            # int test
            'x-archive-meta00-bar': 13,
            
            # list test.
            'x-archive-meta00-subject':'foo',
            'x-archive-meta01-subject': 'bar',
            'x-archive-meta02-subject': 'baz',

            # convert "_" to "--" test (S3 converts "--" to "_").
            'x-archive-meta00-test--ddd': 'sdfsdf',
             
            # dict test.
            'x-archive-meta00-boo': '{"test": "dict"}',
            'x-archive-meta00-test--foo': 'underscore',

            # prepared HTTP headers test.
            'x-archive-size-hint': 19327352832,
            'x-archive-test-header': 'test value',

            # Automatically added.
            'x-archive-meta-scanner': 'Internet Archive Python library {0}'.format(internetarchive.__version__),
            'x-archive-auto-make-bucket': 1,
    }

    for key, value in ias3_headers.items():
        if key == 'Authorization':
            continue
        assert test_output[key] == value
