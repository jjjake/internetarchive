.. _cli:

Command-Line Interface
======================

The ``ia`` command-line tool is installed with the ``internetarchive`` Python module, or :ref:`available as a binary <binaries>`. ``ia`` allows you to interact with various archive.org services from the command-line.

Once you have :ref:`installed ia <installation>` or :ref:`downloaded a binary <binaries>` and :ref:`configured it <configuration>`, you can start exploring the commands documented below.

Quick Start
-----------

If you're not sure where to start, most users start with these commands:

- ``ia download <identifier>`` - :ref:`Download <cli-download>` files or items
- ``ia search '<query>'`` - :ref:`Search <cli-search>` items on archive.org
- ``ia metadata <identifier>`` - :ref:`Read Metadata <cli-metadata>` from an item
- ``ia upload <identifier> <files> -m 'collection:test_collection'`` - :ref:`Upload <cli-upload>` files to archive.org

Check out the help menu to see all available commands:

.. code:: console

    $ ia --help
    usage: ia [-h] [-v] [-c FILE] [-l] [-d] [-i] [-H HOST] {command} ...

    A command line interface to Archive.org.

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -c FILE, --config-file FILE
                            path to configuration file
      -l, --log             enable logging
      -d, --debug           enable debugging
      -i, --insecure        allow insecure connections
      -H HOST, --host HOST  host to connect to (doesn't work for requests made to s3.us.archive.org)
      --user-agent-suffix SUFFIX
                            append SUFFIX to the default User-Agent header

    commands:
      {command}
        account (ac)        Manage an archive.org account. Note: requires admin privileges
        configure (co)      configure 'ia' with your archive.org credentials
        copy (cp)           Copy files from archive.org items
        delete (rm)         Delete files from archive.org items
        download (do)       Download files from archive.org
        flag (fl)           Manage flags
        list (ls)           list files from archive.org items
        metadata (md)       Retrieve and modify archive.org item metadata
        move (mv)           Move and rename files in archive.org items
        reviews (re)        submit and modify reviews for archive.org items
        search (se)         Search items on archive.org
        simplelists (sl)    Manage simplelists
        tasks (ta)          Retrieve information about your archive.org catalog tasks
        upload (up)         Upload files to archive.org

    Documentation for 'ia' is available at:

    	https://archive.org/developers/internetarchive/cli.html

    See 'ia {command} --help' for help on a specific command.

.. _cli-metadata:

Metadata
--------

Reading Metadata
^^^^^^^^^^^^^^^^

You can use ``ia`` to read and write metadata from archive.org. To retrieve all of an item's metadata in JSON, simply:

.. code:: console

    $ ia metadata TripDown1905

A particularly useful tool to use alongside ``ia`` is `jq <https://stedolan.github.io/jq/>`_. ``jq`` is a command-line tool for parsing JSON. For example:

.. code:: console

    $ ia metadata TripDown1905 | jq '.metadata.date'
    "1906"


Modifying Metadata
^^^^^^^^^^^^^^^^^^

Once ``ia`` has been `configured <quickstart.html#configuring>`_, you can modify `metadata <//archive.org/services/docs/api/metadata-schema>`_:

.. code:: console

    $ ia metadata <identifier> --modify="foo:bar" --modify="baz:foooo"

You can remove a metadata field by setting the value of the given field to ``REMOVE_TAG``.
For example, to remove the metadata field ``foo`` from the item ``<identifier>``:

.. code:: console

    $ ia metadata <identifier> --modify="foo:REMOVE_TAG"

Note that some metadata fields (e.g. ``mediatype``) cannot be modified, and must instead be set initially on upload.

The default target to write to is ``metadata``. If you would like to write to another target, such as ``files``, you can specify so using the ``--target`` parameter. For example, if we had an item whose identifier was ``my_identifier`` and we wanted to add a metadata field to a file within the item called ``foo.txt``:

.. code:: console

    $ ia metadata my_identifier --target="files/foo.txt" --modify="title:My File"

You can also create new targets if they don't exist:

.. code:: console

    $ ia metadata <identifier> --target="extra_metadata" --modify="foo:bar"

There is also an ``--append`` option which allows you to append a string to an existing metadata strings (Note: use ``--append-list`` for appending elements to a list).
For example, if your item's title was ``Foo`` and you wanted it to be ``Foo Bar``, you could simply do:

.. code:: console

    $ ia metadata <identifier> --append="title: Bar"

If you would like to add a new value to an existing field that is an array (like ``subject`` or ``collection``), you can use the ``--append-list`` option:

.. code:: console

    $ ia metadata <identifier> --append-list="subject:another subject"

This command would append ``another subject`` to the items list of subjects, if it doesn't already exist (i.e. no duplicate elements are added).

Metadata fields or elements can be removed with the ``--remove`` option:

.. code:: console

    $ ia metadata <identifier> --remove="subject:another subject"

This would remove ``another subject`` from the items subject field, regardless of whether or not the field is a single or multi-value field.


Refer to `Internet Archive Metadata <//archive.org/services/docs/api/metadata-schema/index.html>`_ for more specific details regarding metadata and archive.org.


Modifying Metadata in Bulk
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a lot of metadata changes to submit, you can use a CSV spreadsheet to submit many changes with a single command.
Your CSV must contain an ``identifier`` column, with one item per row. Any other column added will be treated as a metadata field to modify. If no value is provided in a given row for a column, no changes will be submitted. If you would like to specify multiple values for certain fields, an index can be provided: ``subject[0]``, ``subject[1]``. Your CSV file should be UTF-8 encoded. See `metadata.csv <https://archive.org/download/ia-pex/metadata.csv>`_ for an example CSV file.

Once you're ready to submit your changes, you can submit them like so:

.. code:: console

    $ ia metadata --spreadsheet=metadata.csv

See ``ia metadata -- help`` for more details.

.. _cli-upload:

Upload
------

``ia`` can also be used to upload items to archive.org. After `configuring ia <quickstart.html#configuring>`__, you can upload files like so:

.. code:: console

    $ ia upload <identifier> file1 file2 --metadata="mediatype:texts" --metadata="blah:arg"

.. warning:: Please note that, unless specified otherwise, items will be uploaded with a ``data`` mediatype. **This cannot be changed afterwards.** Therefore, you should specify a mediatype when uploading, eg. ``--metadata="mediatype:movies"``. Similarly, if you want your upload to end up somewhere else than the default collection (currently `community texts <//archive.org/details/opensource>`_), you should also specify a collection with ``--metadata="collection:foo"``. See `metadata documentation <//archive.org/services/docs/api/metadata-schema>`_ for more information.

You can upload files from ``stdin``:

.. code:: console

    $ curl http://dumps.wikimedia.org/kywiki/20130927/kywiki-20130927-pages-logging.xml.gz \
      | ia upload <identifier> - --remote-name=kywiki-20130927-pages-logging.xml.gz --metadata="title:Uploaded from stdin."

You can use the ``--retries`` parameter to retry on errors (i.e. if IA-S3 is overloaded):

.. code:: console

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

.. code:: console

    $ ia upload --spreadsheet=uploading.csv

Bulk Uploading Special Columns
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can set a remote filename that differs from your local filename by specifying a remote filename in a column named ``REMOTE_NAME`` (Added to ``ia`` in ``v2.0.0``).

See ``ia upload --help`` for more details.

Setting File-Level Metadata on Upload
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can set file-level metadata at time of upload via a JSON/JSONL file.
The JSON or JSONL must have a dict for each file, with the local path to the file stored under the key, ``name``.
For example, you could upload two files named ``foo.txt`` and ``bar.txt`` with a file-level ``title`` with the following JSONL file (named ``file_md.jsonl``):

.. code:: json

    {"name": "foo.txt", "title": "my foo file"}
    {"name": "bar.txt", "title": "my foo file"}

And the following command:

.. code:: console

    $ ia upload <id> --file-metadata file_md.jsonl


.. _cli-download:

Download
--------


Download an entire item:

.. code:: console

    $ ia download TripDown1905

Download specific files from an item:

.. code:: console

    $ ia download TripDown1905 TripDown1905_512kb.mp4 TripDown1905.ogv

Download specific files matching a glob pattern:

.. code:: console

    $ ia download TripDown1905 --glob="*.mp4"

Note that you may have to escape the ``*`` differently depending on your shell (e.g. ``\*.mp4``, ``'*.mp4'``, etc.).

Download specific files matching a glob pattern, but excluding files matching a different glob pattern:

.. code:: console

    $ ia download TripDown1905 --glob="*.mp4" --exclude "*512kb*"

Note that ``--exclude`` can only be used in conjunction with ``--glob``.

Download files matching multiple glob and exclude patterns:

.. code:: console

    $ ia download TripDown1905 --glob="*.mp4|*.xml" --exclude "*512kb*|*_reviews.xml"

Download only files of a specific format:

.. code:: console

    $ ia download TripDown1905 --format='512Kb MPEG4'

Note that ``--format`` cannot be used with ``--glob`` or ``--exclude``.
You can get a list of the formats of a given item like so:

.. code:: console

    $ ia metadata --formats TripDown1905

Download an entire collection:

.. code:: console

    $ ia download --search 'collection:glasgowschoolofart'

Download from an itemlist:

.. code:: console

    $ ia download --itemlist itemlist.txt

See ``ia download --help`` for more details.


Downloading On-The-Fly Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some files on archive.org are generated on-the-fly as requested. This currently includes non-original files of the formats EPUB, MOBI, DAISY, and archive.org's own MARCXML. These files can be downloaded using the ``--on-the-fly`` parameter:

.. code:: console

    $ ia download goodytwoshoes00newyiala --on-the-fly


Delete
------

You can use ``ia`` to delete files from archive.org items:

.. code:: console

    $ ia delete <identifier> <file>

Delete all files associated with the specified file, including upstream derivatives and the original:

.. code:: console

    $ ia delete <identifier> <file> --cascade

Delete all files in an item:

.. code:: console

    $ ia delete <identifier> --all

Note that ``ia delete`` makes a backup of any files that are deleted.
They are saved to a directory in the item named ``history/files/``.
The files are named in the format ``$key.~N~``.
These files can be deleted like normal files.
You can also prevent the backup from happening on deletes by adding ``-H x-archive-keep-old-version:0`` to your command.

See ``ia delete --help`` for more details.


.. _cli-search:

Search
------

``ia`` can also be used for retrieving archive.org search results in JSON:

.. code:: console

    $ ia search 'subject:"market street" collection:prelinger'

By default, ``ia search`` attempts to return all items meeting the search criteria,
and the results are sorted by item identifier. If you want to just select the top ``n``
items, you can specify a ``page`` and ``rows`` parameter. For example, to get the
top 20 items matching the search 'dogs':

.. code:: console

    $ ia search --parameters="page=1&rows=20" "dogs"

You can use ``ia search`` to create an itemlist:

.. code:: console

    $ ia search 'collection:glasgowschoolofart' --itemlist > itemlist.txt

You can pipe your itemlist into a GNU Parallel command to download items concurrently:

.. code:: console

    $ ia search 'collection:glasgowschoolofart' --itemlist | parallel 'ia download {}'

See ``ia search --help`` for more details.


Tasks
-----

You can also use ``ia`` to retrieve information about your catalog tasks, after `configuring ia <https://github.com/jjjake/internetarchive#configuring>`__.
To retrieve the task history for an item, simply run:

.. code:: console

    $ ia tasks <identifier>

View all of your queued and running archive.org tasks:

.. code:: console

    $ ia tasks

See ``ia tasks --help`` for more details.


List
----

You can list files in an item like so:

.. code:: console

    $ ia list goodytwoshoes00newyiala

See ``ia list --help`` for more details.


Copy
----

You can copy files in archive.org items like so:

.. code:: console

    $ ia copy <src-identifier>/<src-filename> <dest-identifier>/<dest-filename>

If you're copying your file to a new item, you can provide metadata as well:

.. code:: console

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

Performance Tips
----------------

For downloading or processing many items, see :ref:`using GNU Parallel <parallel>`
for concurrent operations.

Getting Help
------------

If you encounter issues, check :ref:`troubleshooting` for common problems and solutions.
