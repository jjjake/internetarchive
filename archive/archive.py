import time
import os
import json

import requests
from lxml import etree
from boto.s3.key import Key
from jsonpatch import make_patch

from config import DotDict, log_in_cookies, log, s3_connection



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
        r = requests.patch(self.metadata_url, params=ptextarams, cookies=log_in_cookies)
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

    def upload(self, files, meta_dict, dry_run=False, derive=True):

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
            k = Key(bucket)
            k.name = filename
            k.set_contents_from_filename(file, headers=headers)
            log.info('Created: http://archive.org/details/%s' % self.identifier)



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
