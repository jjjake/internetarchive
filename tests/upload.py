#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Test uploading through the internetarchive python package.

This test script creates a new archive.org item, and therefore is named in
such a way that py.test does not automatically run it.
"""

import internetarchive as ia
import datetime
import hashlib
import os
import StringIO
import string
import tempfile
import time

import internetarchive.config as ic


s3_conf = ic.get_config().get('s3', {})
access = s3_conf.get('access_key')
secret = s3_conf.get('secret_key')


# get_new_item()
#_________________________________________________________________________________________
def get_new_item():
    """return an ia item object for an item that does not yet exist"""
    now = datetime.datetime.utcnow()
    item_name = 'test_upload_iawrapper_' + now.strftime('%Y_%m_%d_%H%M%S')
    item = ia.Item(item_name)
    if item.exists is False:
        return item

    raise KeyError, 'Could not find a unique item name after 5 tries'


# get_file()
#_________________________________________________________________________________________
def get_file(item_name, file_name):
    """get a file from a newly-created item. Wait for file to land in item, retry if needed"""

    for i in range(5):
        print '  waiting 30 seconds for upload of', file_name
        time.sleep(30)

        item = ia.Item(item_name)
        f = item.get_file(file_name)
        if f is not None:
            return f

    raise KeyError, 'Could not retrieve file after 5 tries'


# upload_stringIO()
#_________________________________________________________________________________________
def upload_stringIO(item, metadata=dict(collection='test_collection')):
    contents = 'hello world'
    name = 'hello_world.txt'
    fh = StringIO.StringIO(contents)
    fh.name = name

    r = item.upload(fh, metadata=metadata, access_key=access,
                    secret_key=secret)

    f = get_file(item.identifier, name)
    assert f.sha1 == hashlib.sha1(contents).hexdigest()


# upload_tempfile()
#_________________________________________________________________________________________
def upload_tempfile(item):
    contents = 'temporary file contents'
    temp_file = tempfile.NamedTemporaryFile(suffix='.txt')

    temp_file.write(contents)
    temp_file.seek(0, os.SEEK_SET)

    item.upload(temp_file.name, metadata= {
            'collection': 'test_collection',
            'description': 'ℛℯα∂α♭ℓℯ ♭ʊ☂ η☺т Ѧ$☾ℐℐ, ¡ooʇ ןnɟǝsn sı uʍop-ǝpısdn' + string.whitespace,
        }, access_key=access, secret_key=secret)
    temp_file.close()

    f = get_file(item.identifier, os.path.basename(temp_file.name))
    assert f.sha1 == hashlib.sha1(contents).hexdigest()


# upload_two_new_tems()
#_________________________________________________________________________________________
def upload_two_new_items():
    first_item = get_new_item()
    second_item = get_new_item()

    upload_stringIO(first_item, metadata={
            'collection': 'test_collection',
            'description': 'testing ia-wrapper {}'.format(first_item.identifier),
        })
    upload_stringIO(second_item, metadata={
            'collection': 'test_collection',
            'description': '',
        })
    first_item.get_metadata()
    second_item.get_metadata()
    assert first_item.metadata['description'] != second_item.metadata['description']


# test_upload()
#_________________________________________________________________________________________
def test_upload():
    print 'Finding new item name'
    item = get_new_item()

    print 'Uploading new item named', item.identifier

    print 'Testing upload using StringIO'
    upload_stringIO(item)

    print 'Testing upload using tempfile'
    upload_tempfile(item)

    print 'Testing that subsequent uploads do not have headers from previous uploads'
    upload_two_new_items()

    print 'Finished upload test'


# main()
#_________________________________________________________________________________________
if __name__ == '__main__':
    if os.environ.get('IAS3_ACCESS_KEY') is None:
        raise LookupError, 'You must set IAS3_ACCESS_KEY environment variable!'

    if os.environ.get('IAS3_SECRET_KEY') is None:
        raise LookupError, 'You must set IAS3_SECRET_KEY environment variable!'

    test_upload()
