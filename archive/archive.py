import time
import os
import json
import math
from multiprocessing import Pool
from filechunkio import FileChunkIO

import requests
from boto.s3.key import Key
from jsonpatch import make_patch

from config import DotDict, log_in_cookies, log, s3_connection


# S3 Multi-Part Upload (Must be outside of class) >>>
#______________________________________________________________________________
def _upload_part(bucketname, multipart_id, part_num, source_path, offset, 
                 bytes, amount_of_retries=10):
    """
    Upload a part of a file with retries.
    """
    def _upload(retries_left=amount_of_retries):
        try:
            log.info('Start uploading part #%d ...' % part_num)
            bucket = s3_connection.get_bucket(bucketname)
            for mp in bucket.get_all_multipart_uploads():
                if mp.id == multipart_id:
                    with FileChunkIO(source_path, 'r', offset=offset, 
                                     bytes=bytes) as fp:
                        mp.upload_part_from_file(fp=fp, part_num=part_num)
                    break
        except Exception, exc:
            if retries_left:
                _upload(retries_left=retries_left - 1)
            else:
                log.info('... Failed uploading part #%d' % part_num)
                raise exc
        else:
            log.info('... Uploaded part #%d' % part_num)
    
    _upload()

class Item(object):

    def __init__(self, identifier):
        self.identifier = identifier
        self.details_url = 'http://archive.org/details/%s' % identifier
        self.download_url = 'http://archive.org/download/%s' % identifier
        self.metadata_url = 'http://archive.org/metadata/%s' % identifier
        self.req = requests.get(self.metadata_url)
        self.metadata = json.loads(self.req.text, object_hook=DotDict)
        if self.metadata == {}:
            self.exists = False
        else:
            self.exists = True


    # METADATA ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
    def write_metadata(self, patch, target="metadata"):
        src = self.metadata[target]
        dest = dict((src.items() + patch.items()))
        patch = make_patch(src, dest) #.patch
        params = {"-patch": json.dumps(patch), "-target": target}
        r = requests.patch(self.metadata_url, params=params, 
                           cookies=log_in_cookies)
        return r


    # UPLOADING ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
    def get_s3_bucket(self, headers={}, make_bucket=False):
        log.debug('Getting Bucket...')
        bucket = s3_connection.lookup(self.identifier)

        if bucket is not None:
            log.debug('Found existing bucket %s' % self.identifier)
            return bucket

        if make_bucket:
            log.debug('Creating new bucket %s' % self.identifier)
            headers['x-archive-queue-derive'] = 0
            bucket = s3_connection.create_bucket(self.identifier,
                                                 headers=headers)
            i=0
            while i<60:
                b = s3_connection.lookup(self.identifier)
                if b:
                    return bucket
                log.debug('Waiting for bucket creation...')
                time.sleep(10)
                i+=1
            raise NameError('Could not create or lookup %s' % self.identifier)

    def upload(self, files, meta_dict, dry_run=False, derive=True, 
               multipart=False):

        headers = {'x-archive-meta-%s' % k: v for k,v in
                   meta_dict.iteritems() if type(v) != list}
        for k,v in meta_dict.iteritems():
            if type(v) == list:
                i=1
                for value in v:
                    key = 'x-archive-meta%02d-%s' % (i, k)
                    headers[key] = value
                    i+=1
        headers = {k: v for k,v in headers.iteritems() if v}

        if dry_run:
            return headers

        if not type(files) == list:
            files = [files]
        for file in files:
            filename = file.split('/')[-1]
            bucket = self.get_s3_bucket(headers, make_bucket=True)
            if bucket.get_key(filename):
                log.warning('File already exists, not deleting from server!')
                return None
            if not derive:
                headers = {'x-archive-queue-derive': 0}
            if multipart is False:
                k = Key(bucket)
                k.name = filename
                k.set_contents_from_filename(file, headers=headers)
                log.info('Upload complete:\t%s' % self.identifier)
            # MULTI-PART UPLOAD ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
            else:
                parallel_processes=4
                keyname = filename
                mp = bucket.initiate_multipart_upload(keyname, headers=headers)
                print mp
                source_size = os.stat(file).st_size
                headers['x-archive-size-hint'] = source_size
                bytes_per_chunk = (max(int(math.sqrt(5242880) * 
                                   math.sqrt(source_size)), 5242880))
                chunk_amount = (int(math.ceil(source_size / 
                                float(bytes_per_chunk))))
                pool = Pool(processes=parallel_processes)
                for i in range(chunk_amount):
                    offset = i * bytes_per_chunk
                    remaining_bytes = source_size - offset
                    bytes = min([bytes_per_chunk, remaining_bytes])
                    part_num = i + 1
                    pool.apply_async(_upload_part, 
                                     [self.identifier, mp.id, part_num, file, 
                                      offset, bytes])
                pool.close()
                pool.join()

                if len(mp.get_all_parts()) == chunk_amount:
                    mp.complete_upload()
                    key = bucket.get_key(keyname)
                    log.info('Upload complete:\t%s' % self.identifier)
                else:
                    mp.cancel_upload()


class Catalog(object):

    def __init__(self, params=None):
        if not params:
            params = {'justme': 1, 'json': 2, 'output': 'json',
                      'callback': 'foo',
            }
        url = 'http://www.us.archive.org/catalog.php'
        r = requests.get(url, params=params, cookies=log_in_cookies)

        # This ugly little line is used to parse the faux JSON available from
        # catalog.php
        self.tasks_json = json.loads(r.text.strip('foo').strip().strip('()'))
        self.tasks = []
        for t in self.tasks_json:
            td = {}
            td['identifier'] = t[0]
            td['server'] = t[1]
            td['command'] = t[2]
            td['time'] = t[3]
            td['submitter'] = t[4]
            td['args'] = t[5]
            td['task_id'] = t[6]
            td['type'] = t[7]
            self.tasks.append(td)

        self.green_rows = [x for x in self.tasks if x['type'] == 0]
        self.blue_rows = [x for x in self.tasks if x['type'] == 1]
        self.red_rows = [x for x in self.tasks if x['type'] == 2]
        self.brown_rows = [x for x in self.tasks if x['type'] == 9]
