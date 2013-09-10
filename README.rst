A python interface to archive.org
---------------------------------

.. image:: https://travis-ci.org/jjjake/ia-wrapper.png?branch=master
        :target: https://travis-ci.org/jjjake/ia-wrapper

.. image:: https://pypip.in/d/internetarchive/badge.png
        :target: https://pypi.python.org/pypi/internetarchive

Please report all bugs and issues on `Github <https://github.com/jjjake/ia-wrapper/issues>`__.

Installation
~~~~~~~~~~~~

You can install this module via pip:

``pip install internetarchive``

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

Uploading from Python
~~~~~~~~~~~~~~~~~~~~~

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

Uploading from the command-line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use the provided ``ia`` command-line tool to upload items:

.. code:: bash

    $ export AWS_ACCESS_KEY_ID='xxx'
    $ export AWS_SECRET_ACCESS_KEY='yyy'

    $ ia upload <identifier> file1 file2 --metadata="title:foo" --metadata="blah:arg"

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

You can also use the provided ``ia`` command-line tool to modify
metadata. Be sure that the AWS\_ACCESS\_KEY\_ID and
AWS\_SECRET\_ACCESS\_KEY environment variables are set.

.. code:: bash

    $ ia metadata <identifier> --modify="foo:bar" --modify="baz:foooo"

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

You can also search using the provided ``ia`` command-line script:

.. code:: bash

    $ ia search 'collection:usenet'

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
