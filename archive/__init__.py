# -*- coding: utf-8 -*-

"""
archive
~~~~~~~

:copyright: (c) 2012 by Jacob M. Johnson.
:license: GPL, see LICENSE for more details.

"""

__title__ = 'archive'
__version__ = '0.1.0'
__author__ = 'Jacob M. Johnson'
__license__ = 'GPL'
__copyright__ = 'Copyright 2012 Jacob M. Johnson'

from .archive import Item, Catalog
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


COOKIES = {'logged-in-sig': os.environ['LOGGED_IN_SIG'],
           'logged-in-user': os.environ['LOGGED_IN_USER'],
}


import boto
from boto.s3.key import Key
from boto.s3.connection import OrdinaryCallingFormat

S3_CONNECTION = boto.connect_s3(host='s3.us.archive.org',
                                calling_format=OrdinaryCallingFormat())


class DotDict(dict):

    def __getattr__(self, attr):
        return self.get(attr, None)

    __setattr__= dict.__setitem__
    __delattr__= dict.__delitem__
