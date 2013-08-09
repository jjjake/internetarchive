# -*- coding: utf-8 -*-
"""
archive.api
~~~~~~~~~~~

This module implements the Archive API.

:copyright: (c) 2013 by Jacob M Johnson.

"""
from . import archive


def upload():
    pass

def modify_metadata():
    pass

def search():
    pass

def download():
    pass

def get_tasks():
    pass


import time
import os
import json
import math
import multiprocessing

import filechunkio
import requests
from boto.s3.connection import S3Connection, OrdinaryCallingFormat
import boto

# UPLOADING ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
def _upload_part(conn, bucketname, multipart_id, part_num, source_path, offset,
                 bytes, amount_of_retries=10):
    """
    Upload a part of a file with retries.
    """
    def _upload(retries_left=amount_of_retries):
        try:
            bucket = conn.get_bucket(bucketname)
            for mp in bucket.get_all_multipart_uploads():
                if mp.id == multipart_id:
                    with filechunkio.FileChunkIO(source_path, 'r',
                                                 offset=offset,
                                                 bytes=bytes) as fp:
                        mp.upload_part_from_file(fp=fp, part_num=part_num)
                    break
        except Exception, exc:
            if retries_left:
                _upload(retries_left=retries_left - 1)
            else:
                raise exc
    _upload()

def _get_s3_conn():
    return S3Connection(host='s3.us.archive.org', is_secure=False,
                        calling_format=OrdinaryCallingFormat())

def _get_s3_bucket(identifier, conn, headers={}, ignore_bucket=False):
    if ignore_bucket is True:
        bucket = None
    else:
        bucket = conn.lookup(identifier)
    if bucket:
        return bucket
    headers['x-archive-queue-derive'] = 0
    bucket = conn.create_bucket(identifier, headers=headers)
    i=0
    while i<60:
        b = conn.lookup(identifier)
        if b:
            return bucket
        time.sleep(10)
        i+=1
    raise NameError('Could not create or lookup %s' % identifier)

def upload(identifier, files, meta_dict={}, headers={}, dry_run=False,
           derive=True, multipart=False, ignore_bucket=False):
    """Upload file(s) to an item. The item will be created if it does not
    exist.

    :param files: Either a list of filepaths, or a string pointing to a single file.
    :param meta_dict: Dictionary of metadata used to create a new item.
    :param dry_run: (optional) Boolean. Set to True to print headers to stdout -- don't upload anything.
    :param derive: (optional) Boolean. Set to False to prevent an item from being derived after upload.
    :param multipart: (optional) Boolean. Set to True to upload files in parts. Useful when uploading large files.
    :param ignore_bucket: (optional) Boolean. Set to True to ignore and clobber existing files and metadata.

    Usage::

        >>> import archive
        >>> archive.upload('item', '/path/to/image.jpg', dict(mediatype='image', creator='Jake Johnson'))
    """
    # ~ Convert metadata from :meta_dict: into S3 headers ~~~~~~~~~~~~~~~~ >
    for key,v in meta_dict.iteritems():
        if type(v) == list:
            i=1
            for value in v:
                s3_header_key = 'x-archive-meta{0:02d}-{1}'.format(i, key)
                headers[s3_header_key] = value.encode('utf-8')
                i+=1
        else:
            s3_header_key = 'x-archive-meta-%s' % key
            if type(v) != int:
                headers[s3_header_key] = v.encode('utf-8')
            else:
                headers[s3_header_key] = v
    headers = {k: str(v) for k,v in headers.iteritems() if v}
    # < ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if dry_run:
        return headers

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ >
    if type(files) != list:
        files = [files]
    for file in files:
        filename = file.split('/')[-1]
        conn = _get_s3_conn()
        bucket = _get_s3_bucket(conn, headers, ignore_bucket=ignore_bucket)
        if bucket.get_key(filename):
            continue
        if not derive:
            headers = {'x-archive-queue-derive': 0}
        if not multipart:
            k = boto.s3.key.Key(bucket)
            k.name = filename
            k.set_contents_from_filename(file, headers=headers)
        # MULTI-PART UPLOAD ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
        else:
            mp = bucket.initiate_multipart_upload(filename, headers=headers)
            source_size = os.stat(file).st_size
            headers['x-archive-size-hint'] = source_size
            bytes_per_chunk = (max(int(math.sqrt(5242880) *
                                       math.sqrt(source_size)), 5242880))
            chunk_amount = (int(math.ceil(source_size /
                            float(bytes_per_chunk))))
            for i in range(chunk_amount):
                offset = i * bytes_per_chunk
                remaining_bytes = source_size - offset
                bytes = min([bytes_per_chunk, remaining_bytes])
                part_num = i + 1
                _upload_part(conn, identifier, mp.id, part_num, file, offset, bytes)
            if len(mp.get_all_parts()) == chunk_amount:
                mp.complete_upload()
                key = bucket.get_key(filename)
            else:
                mp.cancel_upload()
    return True
