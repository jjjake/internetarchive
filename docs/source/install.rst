.. _install:

Installation
============

Installing Internetarchive can be done with `pip <http://www.pip-installer.org/>`_::
    
    $ pip install internetarchive

or, with `easy_install <http://pypi.python.org/pypi/setuptools>`_::

    $ easy_install requests

You can also install a few extra dependencies to help speed things up a bit::
    
    $ pip install "internetarchive[speedups]"

This will install `ujson <https://pypi.python.org/pypi/ujson>`_ for faster JSON parsing,
and `gevent <https://pypi.python.org/pypi/gevent>`_ for concurrent downloads.

If you want to install this module globally on your system instead of inside a ``virtualenv``, use sudo::

    $ sudo pip install internetarchive


Get the Code
------------

Internetarchive is `actively developed on GitHub <https://github.com/jjjake/ia-wrapper>`_.

You can either clone the public repository::

    $ git clone git://github.com/jjjake/ia-wrapper.git

Download the `tarball <https://github.com/jjjake/ia-wrapper/tarball/master>`_::

    $ curl -OL https://github.com/jjjake/ia-wrapper/tarball/master

Or, download the `zipball <https://github.com/jjjake/ia-wrapper/zipball/master>`_::

    $ curl -OL https://github.com/jjjake/ia-wrapper/zipball/master

Once you have a copy of the source, you can install it into your site-packages easily::

    $ python setup.py install
