# -*- coding: utf-8 -*-

"""
internetarchive library
~~~~~~~~~~~~~~~~~~~~~~~

Internetarchive is a python interface to archive.org.
usage:

    >>> import internetarchive
    >>> item = internetarchive.Item('govlawgacode20071')
    >>> item.exists
    True

See the README file for the full documentation, avilable at 
<https://github.com/jjjake/ia-wrapper>.

:copyright: (c) 2013 by Jacob M. Johnson.
:license: GPL, see LICENSE for more details.

"""

__title__ = 'internetarchive'
__version__ = '0.2.9'
__author__ = 'Jacob M. Johnson'
__license__ = 'GPL'
__copyright__ = 'Copyright 2013 Jacob M. Johnson'

from .internetarchive import Item, File, Catalog, Search, Mine
