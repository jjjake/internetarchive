A python interface to archive.org
---------------------------------

.. image:: https://travis-ci.org/jjjake/ia-wrapper.png?branch=master
        :target: https://travis-ci.org/jjjake/ia-wrapper

.. image:: https://pypip.in/d/internetarchive/badge.png
        :target: https://pypi.python.org/pypi/internetarchive

This package installs a CLI tool named ``ia`` for using archive.org from the command-line.
It also installs the ``internetarchive`` python module for programatic access to archive.org.
Please report all bugs and issues on `Github <https://github.com/jjjake/ia-wrapper/issues>`__.

.. contents:: Table of Contents:


Installation
~~~~~~~~~~~~

You can install this module via pip:

``pip install internetarchive``

Alternatively, you can install a few extra dependencies to help speed things up a bit:

``pip install "internetarchive[speedups]"``

This will install `ujson <https://pypi.python.org/pypi/ujson>`__ for faster JSON parsing,
and `gevent <https://pypi.python.org/pypi/gevent>`__ for concurrent downloads.

If you want to install this module globally on your system instead of inside a ``virtualenv``, use sudo:

``sudo pip install internetarchive``


Command-Line Usage
------------------
Help is available by typing ``ia --help``. You can also get help on a command: ``ia <command> --help``.
Available subcommands are ``configure``, ``metadata``, ``upload``, ``download``, ``search``, ``mine``, and ``catalog``.

Downloading
~~~~~~~~~~~

To download the entire `TripDown1905 https://archive.org/details/TripDown1905`__ item:

.. code:: bash

    $ ia download TripDown1905

``ia download`` usage examples:

.. code:: bash

    #download just the mp4 files using ``--glob``
    $ ia download TripDown1905 --glob='*.mp4'

    #download all the mp4 files using ``--formats``:
    $ ia download TripDown1905 --format='512Kb MPEG4'

    #download multiple formats from an item:
    $ ia download TripDown1905 --format='512Kb MPEG4' --format='Ogg Video'

    #list all the formats in an item:
    $ ia metadata --formats TripDown1905

    #download a single file from an item:
    $ ia download TripDown1905 TripDown1905_512kb.mp4

    #download multiple files from an item:
    $ ia download TripDown1905 TripDown1905_512kb.mp4 TripDown1905.ogv


Uploading
~~~~~~~~~

You can use the provided ``ia`` command-line tool to upload items:

.. code:: bash

    $ export AWS_ACCESS_KEY_ID='xxx'
    $ export AWS_SECRET_ACCESS_KEY='yyy'

    $ ia upload <identifier> file1 file2 --metadata="title:foo" --metadata="blah:arg"


Modifying Metadata
~~~~~~~~~~~~~~~~~~

You can use the provided ``ia`` command-line tool to modify
metadata. Be sure that the AWS\_ACCESS\_KEY\_ID and
AWS\_SECRET\_ACCESS\_KEY environment variables are set.

.. code:: bash

    $ ia metadata <identifier> --modify="foo:bar" --modify="baz:foooo"


Searching
~~~~~~~~~

You can search using the provided ``ia`` command-line script:

.. code:: bash

    $ ia search 'collection:usenet'


Python module usage
-------------------

Downloading
~~~~~~~~~~~

The Internet Archive stores data in
`items <http://blog.archive.org/2011/03/31/how-archive-org-items-are-structured/>`__.
You can query the archive using an item identifier:

.. code:: python

    >>> import internetarchive
    >>> item = internetarchive.Item('stairs')
    >>> print item.metadata

Items contains files. You can download the entire item:

.. code:: python

    >>> item.download()

or you can download just a particular file:

.. code:: python

    >>> f = item.file('glogo.png')
    >>> f.download() #writes to disk
    >>> f.download('/foo/bar/some_other_name.png')

You can iterate over files:

.. code:: python

    >>> for f in item.files():
    ...     print f.name, f.sha1

Uploading
~~~~~~~~~

You can use the IA's S3-like interface to upload files to an item. You
need to supply your IAS3 credentials in environment variables in order
to upload. You can retrieve S3 keys from
https://archive.org/account/s3.php

.. code:: python

    >>> import os
    >>> os.environ['AWS_ACCESS_KEY_ID']='x'
    >>> os.environ['AWS_SECRET_ACCESS_KEY']='y'
    >>> item = internetarchive.Item('new_identifier')
    >>> item.upload('/path/to/image.jpg', dict(mediatype='image', creator='Jake Johnson'))

Item-level metadata must be supplied with the first file uploaded to an
item.

You can upload additional files to an existing item:

.. code:: python

    >>> item = internetarchive.Item('existing_identifier')
    >>> item.upload(['/path/to/image2.jpg', '/path/to/image3.jpg'])

You can also upload file-like objects:

.. code:: python

    >>> import StringIO
    >>> fh = StringIO.StringIO('hello world')
    >>> fh.name = 'hello_world.txt
    >>> item.upload(fh)


Modifying Metadata
~~~~~~~~~~~~~~~~~~

You can modify metadata for existing items, using the
``item.modify_metadata()`` function. This uses the `IA Metadata
API <http://blog.archive.org/2013/07/04/metadata-api/>`__ under the hood
and requires your IAS3 credentials.

.. code:: python

    >>> import os
    >>> os.environ['AWS_ACCESS_KEY_ID']='x'
    >>> os.environ['AWS_SECRET_ACCESS_KEY']='y'
    >>> item = internetarchive.Item('my_identifier')
    >>> md = dict(blah='one', foo=['two', 'three'])
    >>> item.modify_metadata(md)


Searching
~~~~~~~~~

You can search for items using the `archive.org advanced search
engine <https://archive.org/advancedsearch.php>`__:

.. code:: python

    >>> import internetarchive
    >>> search = internetarchive.Search('collection:nasa')
    >>> print search.num_found
    186911

You can iterate over your results:

.. code:: python

    >>> for result in search.results: 
    ...     print result['identifier']


A note about uploading items with mixed-case names
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Internet Archive allows mixed-case item identifiers, but Amazon S3
does not allow mixed-case bucket names. The ``internetarchive`` python
module is built on top of the ``boto`` S3 module. ``boto`` disallows
creation of mixed-case buckets, but allows you to download from existing
mixed-case buckets. If you wish to upload a new item to the Internet
Archive with a mixed-case item identifier, you will need to monkey-patch
the ``boto.s3.connection.check_lowercase_bucketname`` function:

.. code:: python

    >>> import boto
    >>> def check_lowercase_bucketname(n):
    ...     return True

    >>> boto.s3.connection.check_lowercase_bucketname = check_lowercase_bucketname

    >>> item = internetarchive.Item('TestUpload_pythonapi_20130812')
    >>> item.upload('file.txt', dict(mediatype='texts', creator='Internet Archive'))
    True
