import logging
import time
import os
import json

import requests
from lxml import etree

from jsonklog.formatters import JSONFormatter
from jsonklog.formatters import JSONFormatterSimple

import boto
from boto.s3.key import Key
from boto.s3.connection import OrdinaryCallingFormat

LOG_FILE = '%s-archive.py.log' % time.strftime("%Y-%m-%d", time.gmtime())
LOG_LEVEL = logging.DEBUG

log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
handler_full = logging.StreamHandler(open(LOG_FILE, 'ab'))
handler_full.setFormatter(JSONFormatter())
logging.Formatter.converter = time.gmtime
log.addHandler(handler_full)

COOKIES = {'logged-in-sig': os.environ['LOGGED_IN_SIG'],
           'logged-in-user': os.environ['LOGGED_IN_USER'],
}

S3_CONNECTION = boto.connect_s3(host='s3.us.archive.org',
                                calling_format=OrdinaryCallingFormat())



class User(object):

    def __init__(self, user):
        self.user = user

    def tasks(self, task_type=None):
        tasks_url = ('http://archive.org/catalog_status.php?'
                     'where=submitter="%s"' % self.user)
        xml_object = etree.parse(tasks_url)
        raw_tasks = {'greenrows': xml_object.find('wait_admin0'),
                     'bluerows': xml_object.find('wait_admin1'),
                     'redrows': xml_object.find('wait_admin2'),
        }
        tasks = {k: v.text for k,v in raw_tasks.iteritems() if v is not None}
        if task_type:
            return tasks.get(task_type)
        else:
            return tasks



class Item(object):

    def __init__(self, identifier):
        self.identifier = identifier
        self.details_url = 'http://archive.org/details/%s' % identifier
        self.download_url = 'http://archive.org/download/%s' % identifier
        self.metadata_url = 'http://archive.org/metadata/%s' % identifier
        self.req = requests.get(self.metadata_url)
        self.metadata = json.loads(self.req.text)
        if self.metadata == {}:
            self.exists = False
        else:
            self.exists = True


    # METADATA ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
    def write_metadata(self, patch, target="metadata"):
        params = json.dumps({"-patch": PATCH, "-target": target})
        url = 'http://archive.org/metadata/%s' % item
        r = requests.patch(self.metadata_url, params=params, cookies=COOKIES)
        return r.text


    # UPLOADING ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~>
    def get_s3_bucket(self, headers={}, make_bucket=False):
        log.debug('Getting Bucket...')
        bucket = S3_CONNECTION.lookup(self.identifier)

        if bucket is not None:
            log.debug('Found existing bucket %s' % self.identifier)
            return bucket

        if make_bucket:
            log.debug('Creating new bucket %s' % self.identifier)
            headers['x-archive-queue-derive'] = 0
            bucket = S3_CONNECTION.create_bucket(self.identifier,
                                                 headers=headers)
            i=0
            while i<60:
                b = S3_CONNECTION.lookup(self.identifier)
                if b:
                    return bucket
                log.debug('Waiting for bucket creation...')
                time.sleep(10)
                i+=1
            raise NameError('Could not create or lookup %s' % self.identifier)

    def upload(self, files, meta_dict):

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

        if not type(files) == list:
            files = [files]
        for file in files:
            filename = file.split('/')[-1]
            bucket = self.get_s3_bucket(headers, make_bucket=True)
            if bucket.get_key(filename):
                log.warning('File already exists, not deleting from server!')
                return None
            k = Key(bucket)
            k.name = filename
            k.set_contents_from_filename(file)
            log.info('Created: http://archive.org/details/%s' % self.identifier)



class Catalog(object):

    def __init__(self, catalog_url):
        url = '%s&json=2&output=json&callback=foo' % catalog_url
        r = requests.get(url, cookies=COOKIES)

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
