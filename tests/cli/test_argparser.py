# -*- coding: utf-8 -*-
import os
import sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)
from internetarchive.cli.argparser import get_args_dict


def test_get_args_dict():
    test_input = [
        'collection:test_collection',
        "description: Attention: multiple colons",
        'unicode_test:தமிழ்',
        'subject:subject1, subject1',
        'subject:subject2',
        'subject:subject3; subject3',
    ]
    test_output = {
        'collection': 'test_collection',
        'description': " Attention: multiple colons",
        'unicode_test': 'தமிழ்',
        'subject': ['subject1, subject1', 'subject2', 'subject3; subject3'],
    }
    args_dict = get_args_dict(test_input)
    for key, value in args_dict.items():
        print(key, value)
        assert test_output[key] == value


def test_get_args_dict_query_string():
    test_input = ['a=b,foo&c=d&e=f', 'foo:bar ']
    test_output = {
        'a': 'b,foo',
        'c': 'd',
        'e': 'f',
        'foo': 'bar ',
    }
    args_dict = get_args_dict(test_input, query_string=True)
    for key, value in args_dict.items():
        assert test_output[key] == value
