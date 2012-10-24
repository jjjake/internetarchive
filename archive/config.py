# -*- coding: utf-8 -*-
import logging
import time
import os

from jsonklog.formatters import JSONFormatter
from jsonklog.formatters import JSONFormatterSimple

LOG_FILE = '%s-archive.py.log' % time.strftime("%Y-%m-%d", time.gmtime())
LOG_LEVEL = logging.DEBUG

log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
handler_full = logging.StreamHandler(open(LOG_FILE, 'ab'))
handler_full.setFormatter(JSONFormatter())
logging.Formatter.converter = time.gmtime
log.addHandler(handler_full)


log_in_cookies = {'logged-in-sig': os.environ['LOGGED_IN_SIG'],
                  'logged-in-user': os.environ['LOGGED_IN_USER'],
}


# S3
#import boto
#from boto.s3.connection import OrdinaryCallingFormat
#s3_connection = boto.connect_s3(host='s3.us.archive.org', is_secure=False,
#                                calling_format=OrdinaryCallingFormat())


from boto.s3.connection import S3Connection
s3_connection = S3Connection(host='s3.us.archive.org', is_secure=False)


class DotDict(dict):

    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__
