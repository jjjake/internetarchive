A Python and Command-Line Interface to Archive.org
--------------------------------------------------

.. image:: https://travis-ci.org/jjjake/internetarchive.svg
    :target: https://travis-ci.org/jjjake/internetarchive

.. image:: https://img.shields.io/pypi/dm/internetarchive.svg
    :target: https://pypi.python.org/pypi/internetarchive

This package installs a command-line tool named ``ia`` for using Archive.org from the command-line.
It also installs the ``internetarchive`` Python module for programatic access to archive.org.
Please report all bugs and issues on `Github <https://github.com/jjjake/ia-wrapper/issues>`__.


Installation
~~~~~~~~~~~~

You can install this module via pip:

.. code:: bash

    $ pip install internetarchive

Binaries of the command-line tool are also available:

.. code:: bash

    $ curl -LO https://archive.org/download/ia-pex/ia
    $ chmod +x ia
    $ ./ia help


Configuring
~~~~~~~~~~~
You can configure both the ``ia`` command-line tool and the Python interface from the command-line:

.. code:: bash

    $ ia configure

You will be prompted to enter your Archive.org login credentials. If authorization is successful a config file will be saved
on your computer that contains your Archive.org S3 keys for uploading and modifying metadata.


Command-Line Usage
------------------
Help is available via ``ia help``. You can also get help on a specific command: ``ia help <command>``.
Available commands::

    help      Retrieve help for subcommands.
    configure Configure `ia`.
    metadata  Retrieve and modify metadata for items on Archive.org.
    upload    Upload items to Archive.org.
    download  Download files from Archive.org.
    delete    Delete files from Archive.org.
    search    Search items on Archive.org.
    tasks     Retrieve information about your Archive.org catalog tasks.
    list      List files in a given item.


Metadata
~~~~~~~~

You can use ``ia`` to read and write metadata from Archive.org. To retrieve all of an items metadata in JSON, simply:

.. code:: bash

    $ ia metadata TripDown1905

You can also modify metadata after `configuring ia <https://github.com/jjjake/internetarchive#configuring>`__.

.. code:: bash

    $ ia metadata <identifier> --modify="foo:bar" --modify="baz:foooo"

See ``ia help metadata`` for more details.


Upload
~~~~~~

``ia`` cand also be used to upload items to Archive.org. After `configuring ia <https://github.com/jjjake/internetarchive#configuring>`__,
you can upload files like so:

.. code:: bash

    $ ia upload <identifier> file1 file2 --metadata="title:foo" --metadata="blah:arg"

You can upload files from ``stdin``:

.. code:: bash

    $ curl http://dumps.wikimedia.org/kywiki/20130927/kywiki-20130927-pages-logging.xml.gz \
      | ia upload <identifier> - --remote-name=kywiki-20130927-pages-logging.xml.gz --metadata="title:Uploaded from stdin."

You can use the ``--retries`` parameter to retry on errors (i.e. if IA-S3 is overloaded):

.. code:: bash
    
    $ ia upload <identifier> file1 --retries 10

See ``ia help upload`` for more details.


Download
~~~~~~~~

Download an entire item:

.. code:: bash

    $ ia download TripDown1905

Download specific files from an item:

.. code:: bash

    $ ia download TripDown1905 TripDown1905_512kb.mp4 TripDown1905.ogv

Download specific files matching a glob pattern:

.. code:: bash

    $ ia download TripDown1905 --glob='*.mp4'

Download only files of a specific format:

.. code:: bash

    $ ia download TripDown1905 --format='512Kb MPEG4'

You can get a list of the formats a given item like so:

.. code:: bash

    $ ia metadata --formats TripDown1905

Download an entire collection:

.. code:: bash

    $ ia download --search 'collection:freemusicarchive'

Download from an itemlist:

.. code:: bash

    $ ia download --itemlist itemlist.txt

See ``ia help download`` for more details.


Delete
~~~~~~

You can use ``ia`` to delete files from Archive.org items:

.. code:: bash

    $ ia delete <identifier> <file>

Delete a file *and* all files derived from the specified file:

.. code:: bash

    $ ia delete <identifier> <file> --cascade

Delete all files in an item:

.. code:: bash

    $ ia delete <identifier> --all

See ``ia help delete`` for more details.


Search
~~~~~~

``ia`` can also be used for retrieving Archive.org search results in JSON:

.. code:: bash

    $ ia search 'subject:"market street" collection:prelinger'
    
By default, ``ia search`` attempts to return all items meeting the search criteria,
and the results are sorted by item identifier. If you want to just select the top ``n``
items, you can specify a ``page`` and ``rows`` parameter. For example, to get the 
top 20 items matching the search 'dogs':

.. code:: bash

    $ ia search --parameters="page:1" --parameters="rows:20" "dogs"

You can use ``ia search`` to create an itemlist:

.. code:: bash

    $ ia search 'collection:freemusicarchive' --itemlist > itemlist.txt

You can pipe your itemlist into a GNU Parallel command to download items concurrently:

.. code:: bash

    $ ia search 'collection:freemusicarchive' --itemlist | parallel 'ia download {}'

See ``ia help search`` for more details.


Tasks
~~~~~

You can also use ``ia`` to retrieve information about your catalog tasks, after `configuring ia <https://github.com/jjjake/internetarchive#configuring>`__.
To retrieve the task history for an item, simply run:

.. code:: bash

    $ ia tasks <identifier>

View all of your queued and running Archive.org tasks:

.. code:: bash

    $ ia tasks

See ``ia help tasks`` for more details.


List
~~~~

You can list files in an item like so:

.. code:: bash

    $ ia list goodytwoshoes00newyiala

See ``ia help list`` for more details.


Python module usage
-------------------

Below is brief overview of the ``internetarchive`` Python library.
Please refer to the `API documentation <http://internetarchive.readthedocs.org/en/latest/>`__ for more specific details.


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
    >>> f.download()
    >>> f.download('/foo/bar/some_other_name.png')


Uploading from Python
~~~~~~~~~~~~~~~~~~~~~

You can use the IA's S3-like interface to upload files to an item after
`configuring the internetarchive library <https://github.com/jjjake/internetarchive#configuring>`__.

.. code:: python

    >>> from internetarchive import get_item
    >>> item = get_item('new_identifier')
    >>> md = dict(mediatype='image', creator='Jake Johnson')
    >>> item.upload('/path/to/image.jpg', metadata=md)

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

You can modify metadata for existing items, using the ``item.modify_metadata()`` function. This uses the `IA Metadata
API <http://blog.archive.org/2013/07/04/metadata-api/>`__ under the hood and requires your IAS3 credentials. So, once
again make sure you have the `internetarchive library configured <https://github.com/jjjake/internetarchive#configuring>`__.

.. code:: python

    >>> from internetarchive import get_item
    >>> item = get_item('my_identifier')
    >>> md = dict(blah='one', foo=['two', 'three'])
    >>> item.modify_metadata(md)


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
