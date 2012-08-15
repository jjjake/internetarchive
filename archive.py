__author__ = "Jake Johnson (jake@archive.org)"
__version__ = "0.1"
__license__ = "Public Domain"

import logging
import time
import os
import json

from jsonklog.formatters import JSONFormatter
from jsonklog.formatters import JSONFormatterSimple
import requests
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

class Item(object):

    def __init__(self, identifier):
        self.identifier = identifier
        self.details_url = 'http://archive.org/details/%s' % identifier
        self.download_url = 'http://archive.org/download/%s' % identifier
        self.metadata_url = 'http://archive.org/metadata/%s' % identifier
        self.req = requests.get(self.metadata_url)
        self.metadata = json.loads(self.req.text)

    # S3 Uploader >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    #__________________________________________________________________________
    def get_bucket(self, headers):
        log.debug('Getting Bucket...')
        bucket = S3_CONNECTION.lookup(self.identifier)

        if bucket is not None:
            log.debug('Found existing bucket %s' % self.identifier)
            return bucket

        log.debug('Creating new bucket %s' % self.identifier)
        headers['x-archive-queue-derive'] = 0
        bucket = S3_CONNECTION.create_bucket(self.identifier, headers=headers)
        i=0
        while i<60:
            b = S3_CONNECTION.lookup(self.identifier)
            if b:
                return bucket
            log.debug('Waiting for bucket creation...')
            time.sleep(10)
            i+=1
        raise NameError('Could not create or lookup ' + self.identifier)

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
            bucket = self.get_bucket(headers)
            if bucket.get_key(filename):
                log.warning('File already exists, not deleting from server!')
                return None
            k = Key(bucket)
            k.name = filename
            k.set_contents_from_filename(file)
            log.info('Created: http://archive.org/details/%s' % self.identifier)
