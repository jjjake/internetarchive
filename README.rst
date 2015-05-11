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
Available subcommands are ``configure``, ``metadata``, ``upload``, ``download``, ``search``, ``delete``, ``list``, and ``catalog``.


Downloading
~~~~~~~~~~~

To download the entire `TripDown1905 <https://archive.org/details/TripDown1905>`__ item:

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

You can use the provided ``ia`` command-line tool to upload items. You
need to supply your IAS3 credentials in environment variables in order
to upload. You can retrieve S3 keys from
https://archive.org/account/s3.php

.. code:: bash

    $ export IAS3_ACCESS_KEY='xxx'
    $ export IAS3_SECRET_KEY='yyy'

    #upload files:
    $ ia upload <identifier> file1 file2 --metadata="title:foo" --metadata="blah:arg"

    #upload from `stdin`:
    $ curl http://dumps.wikimedia.org/kywiki/20130927/kywiki-20130927-pages-logging.xml.gz |
      ia upload <identifier> - --remote-name=kywiki-20130927-pages-logging.xml.gz --metadata="title:Uploaded from stdin."

Metadata
~~~~~~~~

You can use the ``ia`` command-line tool to download item metadata in JSON format:

.. code:: bash

    $ ia metadata TripDown1905

You can also modify metadata. Be sure that the IAS3\_ACCESS\_KEY and
IAS3\_SECRET\_KEY environment variables are set.

.. code:: bash

    $ ia metadata <identifier> --modify="foo:bar" --modify="baz:foooo"

Data Mining
~~~~~~~~~~~

IA Mine can be used for data mining Archive.org metadata and search results: `https://github.com/jjjake/iamine <https://github.com/jjjake/iamine>`__.

Searching
~~~~~~~~~

You can search using the provided ``ia`` command-line script:

.. code:: bash

    $ ia search 'subject:"market street" collection:prelinger'


Parallel Downloading
~~~~~~~~~~~~~~~~~~~~

If you have the GNU ``parallel`` tool intalled, then you can combine ``ia search`` and ``ia metadata`` to quickly retrieve data for many items in parallel:

.. code:: bash

    $ia search 'subject:"market street" collection:prelinger' | parallel -j40 'ia metadata {} > {}_meta.json'



Python module usage
-------------------

Below is brief overview of the ``internetarchive`` Python library.
Please refer to the `API documentation <http://ia-wrapper.readthedocs.org/en/latest/>`__ for more specific details.

Downloading from Python
~~~~~~~~~~~~~~~~~~~~~~~

The Internet Archive stores data in
`items <http://blog.archive.org/2011/03/31/how-archive-org-items-are-structured/>`__.
You can query the archive using an item identifier:

.. code:: python

    >>> from internetarchive import get_item
    >>> item = get_item('stairs')
    >>> print(item.metadata)

Items contains files. You can download the entire item:

.. code:: python

    >>> item.download()

or you can download just a particular file:

.. code:: python

    >>> f = item.get_file('glogo.png')
    >>> f.download() #writes to disk
    >>> f.download('/foo/bar/some_other_name.png')

You can iterate over files:

.. code:: python

    >>> for f in item.iter_files():
    ...     print(f.name, f.sha1)

Uploading from Python
~~~~~~~~~~~~~~~~~~~~~

You can use the IA's S3-like interface to upload files to an item. You
need to supply your IAS3 credentials in environment variables in order
to upload. You can retrieve S3 keys from
https://archive.org/account/s3.php

.. code:: python

    >>> from internetarchive import get_item
    >>> item = get_item('new_identifier')
    >>> md = dict(mediatype='image', creator='Jake Johnson')
    >>> item.upload('/path/to/image.jpg', metadata=md, access_key='xxx', secret_key='yyy')

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
    >>> fh.name = 'hello_world.txt'
    >>> item.upload(fh)


Modifying Metadata from Python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can modify metadata for existing items, using the
``item.modify_metadata()`` function. This uses the `IA Metadata
API <http://blog.archive.org/2013/07/04/metadata-api/>`__ under the hood
and requires your IAS3 credentials.

.. code:: python

    >>> from internetarchive import get_item
    >>> item = get_item('my_identifier')
    >>> md = dict(blah='one', foo=['two', 'three'])
    >>> item.modify_metadata(md, access_key='xxx', secret_key='yyy')


Searching from Python
~~~~~~~~~~~~~~~~~~~~~

You can search for items using the `archive.org advanced search
engine <https://archive.org/advancedsearch.php>`__:

.. code:: python

    >>> from internetarchive import search_items
    >>> search = search_items('collection:nasa')
    >>> print(search.num_found)
    186911

You can iterate over your results:

.. code:: python

    >>> for result in search:
    ...     print(result['identifier'])
