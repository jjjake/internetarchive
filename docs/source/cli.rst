Command-Line Interface
======================

The ``ia`` command-line tool is installed with ``internetarchive``, or `available as a binary <installation.html#binaries>`_. ``ia`` allows you to interact with various archive.org services from the command-line.

Getting Started
---------------

The easiest way to start using ``ia`` is downloading a binary. The only requirements of the binary are a Unix-like environment with Python installed. To download the latest binary, and make it executable simply:

.. code:: bash

    $ curl -LOs https://archive.org/download/ia-pex/ia
    $ chmod +x ia
    $ ./ia help
    A command line interface to archive.org.

    usage:
        ia [--help | --version]
        ia [--config-file FILE] [--log | --debug] [--insecure] <command> [<args>]...

    options:
        -h, --help
        -v, --version
        -c, --config-file FILE  Use FILE as config file.
        -l, --log               Turn on logging [default: False].
        -d, --debug             Turn on verbose logging [default: False].
        -i, --insecure          Use HTTP for all requests instead of HTTPS [default: false]

    commands:
        help      Retrieve help for subcommands.
        configure Configure `ia`.
        metadata  Retrieve and modify metadata for items on archive.org.
        upload    Upload items to archive.org.
        download  Download files from archive.org.
        delete    Delete files from archive.org.
        search    Search archive.org.
        tasks     Retrieve information about your archive.org catalog tasks.
        list      List files in a given item.

    See 'ia help <command>' for more information on a specific command.


Metadata
--------

Reading Metadata
^^^^^^^^^^^^^^^^

You can use ``ia`` to read and write metadata from archive.org. To retrieve all of an item's metadata in JSON, simply:

.. code:: bash

    $ ia metadata TripDown1905

A particularly useful tool to use alongside ``ia`` is `jq <https://stedolan.github.io/jq/>`_. ``jq`` is a command-line tool for parsing JSON. For example:

.. code:: bash

    $ ia metadata TripDown1905 | jq '.metadata.date'
    "1906"


Modifying Metadata
^^^^^^^^^^^^^^^^^^

Once ``ia`` has been `configured <quickstart.html#configuring>`_, you can modify metadata:

.. code:: bash

    $ ia metadata <identifier> --modify="foo:bar" --modify="baz:foooo"

You can remove a metadata field by setting the value of the given field to ``REMOVE_TAG``.
For example, to remove the metadata field ``foo`` from the item ``<identifier>``:

.. code:: bash

    $ ia metadata <identifier> --modify="foo:REMOVE_TAG"

Note that some metadata fields (e.g. ``mediatype``) cannot be modified, and must instead be set initially on upload.

The default target to write to is ``metadata``. If you would like to write to another target, such as ``files``, you can specify so using the ``--target`` parameter. For example, if we had an item whose identifier was ``my_identifier`` and we wanted to add a metadata field to a file within the item called ``foo.txt``: 

.. code:: bash

    $ ia metadata my_identifier --target="files/foo.txt" --modify="title:My File"

You can also create new targets if they don't exist:

.. code:: bash

    $ ia metadata <identifier> --target="extra_metadata" --modify="foo:bar"

There is also an ``--append`` option which allows you to append a string to an existing metadata strings (Note: use ``--append-list`` for appending elments to a list).
For example, if your item's title was ``Foo`` and you wanted it to be ``Foo Bar``, you could simply do:

.. code:: bash

    $ ia metadata <identifier> --append="title: Bar"

If you would like to add a new value to an existing field that is an array (like ``subject`` or ``collection``), you can use the ``--append-list`` option:

.. code:: bash

    $ ia metadata <identifier> --append-list="subject:another subject"

This command would append ``another subject`` to the items list of subjects, if it doesn't already exist (i.e. no duplicate elements are added).

Metadata fields or elements can be removed with the ``--remove`` option:

.. code:: bash

    $ ia metadata <identifier> --remove="subject:another subject"

This would remove ``another subject`` from the items subject field, regardless of whether or not the field is a single or multi-value field.


Refer to `Internet Archive Metadata <//archive.org/services/docs/api/metadata-schema/index.html>`_ for more specific details regarding metadata and archive.org.


Modifying Metadata in Bulk
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a lot of metadata changes to submit, you can use a CSV spreadsheet to submit many changes with a single command.
Your CSV must contain an ``identifier`` column, with one item per row. Any other column added will be treated as a metadata field to modify. If no value is provided in a given row for a column, no changes will be submitted. If you would like to specify multiple values for certain fields, an index can be provided: ``subject[0]``, ``subject[1]``. Your CSV file should be UTF-8 encoded. See `metadata.csv <https://archive.org/download/ia-pex/metadata.csv>`_ for an example CSV file.

Once you're ready to submit your changes, you can submit them like so:

.. code:: bash

    $ ia metadata --spreadsheet=metadata.csv

See ``ia help metadata`` for more details.


Upload
------

``ia`` can also be used to upload items to archive.org. After `configuring ia <quickstart.html#configuring>`__, you can upload files like so:

.. code:: bash

    $ ia upload <identifier> file1 file2 --metadata="mediatype:texts" --metadata="blah:arg"

.. warning:: Please note that, unless specified otherwise, items will be uploaded with a ``data`` mediatype. **This cannot be changed afterwards.** Therefore, you should specify a mediatype when uploading, eg. ``--metadata="mediatype:movies"``. Similarly, if you want your upload to end up somewhere else than the default collection (currently `community texts <https://archive.org/details/opensource>`_), you should also specify a collection with ``--metadata="collection:foo"``.

You can upload files from ``stdin``:

.. code:: bash

    $ curl http://dumps.wikimedia.org/kywiki/20130927/kywiki-20130927-pages-logging.xml.gz \
      | ia upload <identifier> - --remote-name=kywiki-20130927-pages-logging.xml.gz --metadata="title:Uploaded from stdin."

You can use the ``--retries`` parameter to retry on errors (i.e. if IA-S3 is overloaded):

.. code:: bash
    
    $ ia upload <identifier> file1 --retries 10

Note that ``ia upload`` makes a backup of any files that are clobbered.
They are saved to a directory in the item named ``history/files/``.
The files are named in the format ``$key.~N~``.
These files can be deleted like normal files.
You can also prevent the backup from happening on clobbers by adding ``-H x-archive-keep-old-version:0`` to your command.

Refer to `archive.org Identifiers <//archive.org/services/docs/api/metadata-schema/index.html#archive-org-identifiers>`_ for more information on creating valid archive.org identifiers.
Please also read the `Internet Archive Items <//archive.org/services/docs/api/items.html>`_ page before getting started.

Bulk Uploading
^^^^^^^^^^^^^^

Uploading in bulk can be done similarly to `Modifying Metadata in Bulk`_. The only difference is that you must provide a ``file`` column which contains a relative or absolute path to your file. Please see `uploading.csv <https://archive.org/download/ia-pex/uploading.csv>`_ for an example.

Once you are ready to start your upload, simply run:

.. code:: bash

    $ ia upload --spreadsheet=uploading.csv


See ``ia help upload`` for more details.


Download
--------


Download an entire item:

.. code:: bash

    $ ia download TripDown1905

Download specific files from an item:

.. code:: bash

    $ ia download TripDown1905 TripDown1905_512kb.mp4 TripDown1905.ogv

Download specific files matching a glob pattern:

.. code:: bash

    $ ia download TripDown1905 --glob="*.mp4"

Note that you may have to escape the ``*`` differently depending on your shell (e.g. ``\*.mp4``, ``'*.mp4'``, etc.).

Download only files of a specific format:

.. code:: bash

    $ ia download TripDown1905 --format='512Kb MPEG4'

Note that ``--format`` cannot be used with ``--glob``.
You can get a list of the formats of a given item like so:

.. code:: bash

    $ ia metadata --formats TripDown1905

Download an entire collection:

.. code:: bash

    $ ia download --search 'collection:glasgowschoolofart'

Download from an itemlist:

.. code:: bash

    $ ia download --itemlist itemlist.txt

See ``ia help download`` for more details.


Downloading On-The-Fly Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some files on archive.org are generated on-the-fly as requested. This currently includes non-original files of the formats EPUB, MOBI, DAISY, and archive.org's own MARC XML. These files can be downloaded using the ``--on-the-fly`` parameter:

.. code:: bash

    $ ia download goodytwoshoes00newyiala --on-the-fly


Delete
------

You can use ``ia`` to delete files from archive.org items:

.. code:: bash

    $ ia delete <identifier> <file>

Delete a file *and* all files derived from the specified file:

.. code:: bash

    $ ia delete <identifier> <file> --cascade

Delete all files in an item:

.. code:: bash

    $ ia delete <identifier> --all

Note that ``ia delete`` makes a backup of any files that are deleted.
They are saved to a directory in the item named ``history/files/``.
The files are named in the format ``$key.~N~``.
These files can be deleted like normal files.
You can also prevent the backup from happening on deletes by adding ``-H x-archive-keep-old-version:0`` to your command.

See ``ia help delete`` for more details.


Search
------

``ia`` can also be used for retrieving archive.org search results in JSON:

.. code:: bash

    $ ia search 'subject:"market street" collection:prelinger'
    
By default, ``ia search`` attempts to return all items meeting the search criteria,
and the results are sorted by item identifier. If you want to just select the top ``n``
items, you can specify a ``page`` and ``rows`` parameter. For example, to get the 
top 20 items matching the search 'dogs':

.. code:: bash

    $ ia search --parameters="page=1&rows=20" "dogs"

You can use ``ia search`` to create an itemlist:

.. code:: bash

    $ ia search 'collection:glasgowschoolofart' --itemlist > itemlist.txt

You can pipe your itemlist into a GNU Parallel command to download items concurrently:

.. code:: bash

    $ ia search 'collection:glasgowschoolofart' --itemlist | parallel 'ia download {}'

See ``ia help search`` for more details.


Tasks
-----

You can also use ``ia`` to retrieve information about your catalog tasks, after `configuring ia <https://github.com/jjjake/internetarchive#configuring>`__.
To retrieve the task history for an item, simply run:

.. code:: bash

    $ ia tasks <identifier>

View all of your queued and running archive.org tasks:

.. code:: bash

    $ ia tasks

See ``ia help tasks`` for more details.


List
----

You can list files in an item like so:

.. code:: bash

    $ ia list goodytwoshoes00newyiala

See ``ia help list`` for more details.


Copy
----

You can copy files in archive.org items like so:

.. code:: bash

    $ ia copy <src-identifier>/<src-filename> <dest-identifier>/<dest-filename>

If you're copying your file to a new item, you can provide metadata as well:

.. code:: bash

    $ ia copy <src-identifier>/<src-filename> <dest-identifier>/<dest-filename> --metadata 'title:My New Item' --metadata collection:test_collection

Note that ``ia copy`` makes a backup of any files that are clobbered.
They are saved to a directory in the item named ``history/files/``.
The files are named in the format ``$key.~N~``.
These files can be deleted like normal files.
You can also prevent the backup from happening on clobbers by adding ``-H x-archive-keep-old-version:0`` to your command.

Move
----

``ia move`` works just like ``ia copy`` except the source file is deleted after the file has been successfully copied.

Note that ``ia move`` makes a backup of any files that are clobbered or deleted.
They are saved to a directory in the item named ``history/files/``.
The files are named in the format ``$key.~N~``.
These files can be deleted like normal files.
You can also prevent the backup from happening on clobbers or deletes by adding ``-H x-archive-keep-old-version:0`` to your command.
