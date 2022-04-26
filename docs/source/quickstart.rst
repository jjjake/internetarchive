.. _quickstart:

Quickstart
==========


Configuring
-----------

Certain functionality of the internetarchive Python library requires your archive.org credentials.
Your `IA-S3 keys <https://archive.org/account/s3.php>`_ are required for uploading, searching, and modifying metadata, and your archive.org logged-in cookies are required for downloading access-restricted content and viewing your task history.
To automatically create a config file with your archive.org credentials, you can use the ``ia`` command-line tool::

    $ ia configure
    Enter your archive.org credentials below to configure 'ia'.

    Email address: user@example.com
    Password:

    Config saved to: /home/user/.config/ia.ini

Your config file will be saved to ``$HOME/.config/ia.ini``, or ``$HOME/.ia`` if you do not have a ``.config`` directory in ``$HOME``. Alternatively, you can specify your own path to save the config to via ``ia --config-file '~/.ia-custom-config' configure``.

If you have a netc file with your archive.org credentials in it, you can simply run ``ia configure --netrc``.
Note that Python's netrc library does not currently support passphrases, or passwords with spaces in them, and therefore are not currently supported here.

Uploading
---------

Creating a new `item on archive.org <//archive.org/services/docs/api/items.html>`_ and uploading files to it is as easy as::

    >>> from internetarchive import upload
    >>> md = {'collection': 'test_collection', 'title': 'My New Item', 'mediatype': 'movies'}
    >>> r = upload('<identifier>', files=['foo.txt', 'bar.mov'], metadata=md)
    >>> r[0].status_code
    200

You can set remote filename using a dictionary::

    >>> r = upload('<identifier>', files={'remote-name.txt': 'local-name.txt'})

You can upload file-like objects::

    >>> r = upload('iacli-test-item301', {'foo.txt': StringIO('bar baz boo')})

If the item already has a file with the same filename, the existing file within the item will be overwritten.

:func:`upload <internetarchive.upload>` can also upload directories. For example, the following command will upload ``my_dir`` and all of it's contents to ``https://archive.org/download/my_item/my_dir/``::

    >>> r = upload('my_item', 'my_dir')

To upload only the contents of the directory, but not the directory itself, simply append a slash to your directory::

    >>> r = upload('my_item', 'my_dir/')

This will upload all of the contents of ``my_dir`` to ``https://archive.org/download/my_item/``. :func:`upload <internetarchive.upload>` accepts relative or absolute paths.

Setting File-Level Metadata on Upload
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can set file-level metadata at time of upload via a Python dict or list of dicts.
The only requirement is that there is a dict for each file with the local path to the file stored under the ``name`` key.
For example::

    >>> r = upload('my_item', {'name': 'foo.txt', 'title': 'My File'})
    >>> r = upload('my_item', [{'name': 'foo.txt', 'title': 'My File'}, {'name': 'bar.txt', 'title': 'My Other File'}])

**Note**: metadata can only be added to an item using the :func:`upload <internetarchive.upload>` function on item creation. If an item already exists and you would like to modify it's metadata, you must use :func:`modify_metadata <internetarchive.modify_metadata>`.


Metadata
--------

Reading Metadata
^^^^^^^^^^^^^^^^

You can access all of an item's metadata via the :class:`Item <internetarchive.Item>` object::

    >>> from internetarchive import get_item
    >>> item = get_item('nasa')
    >>> item.item_metadata['metadata']['title']
    'NASA Images'

:func:`get_item <internetarchive.get_item>` retrieves all of an item's metadata via the `Internet Archive Metadata API <http://blog.archive.org/2013/07/04/metadata-api/>`_. This metadata can be accessed via the ``Item.item_metadata`` attribute::

    >>> item.item_metadata.keys()
    dict_keys(['created', 'updated', 'd2', 'uniq', 'metadata', 'item_size', 'dir', 'd1', 'files', 'server', 'files_count', 'workable_servers'])

All of the top-level keys in ``item.item_metadata`` are available as attributes::

    >>> item.server
    'ia802606.us.archive.org'
    >>> item.item_size
    126586
    >>> item.files[0]['name']
    'NASAarchiveLogo.jpg'
    >>> item.metadata['identifier']
    'nasa'


Writing Metadata
^^^^^^^^^^^^^^^^

Adding new metadata to an item can be done using the :func:`modify_metadata <internetarchive.modify_metadata>` function::

    >>> from internetarchive import modify_metadata
    >>> r = modify_metadata('<identifier>', metadata={'title': 'My Stuff'})
    >>> r.status_code
    200

Modifying metadata can also be done via the :class:`Item <internetarchive.Item>` object. For example, changing the title we set in the example above can be done like so::

    >>> r = item.modify_metadata({'title': 'My New Title'})
    >>> item.metadata['title']
    'My New Title'

To remove a metadata field from an item's metadata, set the value to ``'REMOVE_TAG'``::

    >>> r = item.modify_metadata({'foo': 'new metadata field.'})
    >>> item.metadata['foo']
    'new metadata field.'
    >>> r = item.modify_metadata({'foo': 'REMOVE_TAG'})
    >>> print(item.metadata.get('foo'))
    None

The default behaviour of :func:`modify_metadata <internetarchive.modify_metadata>` is to modify item-level metadata (i.e. title, description, etc.). If we want to modify different kinds of metadata, say the metadata of a specific file, we have to change the metadata ``target`` in the call to :func:`modify_metadata <internetarchive.modify_metadata>`::

    >>> r = item.modify_metadata({'title': 'My File Title'}, target='files/foo.txt')
    >>> f = item.get_file('foo.txt')
    >>> f.title
    'My File Title'

Refer to `Internet Archive Metadata <//archive.org/services/docs/api/metadata-schema/index.html>`_ for more specific details regarding metadata and archive.org.


Downloading
-----------

Downloading files can be done via the :func:`download <internetarchive.download>` function::

    >>> from internetarchive import download
    >>> download('nasa', verbose=True)
    nasa:
     downloading __ia_thumb.jpg: 100%|███████████████████████| 5.25k/5.25k [00:00<00:00, 2.67MiB/s]
     downloading globe_west_540.jpg: 100%|████████████████████| 64.5k/64.5k [00:00<00:00, 420kiB/s]
     downloading globe_west_540_thumb.jpg: 100%|█████████████| 6.02k/6.02k [00:00<00:00, 6.92MiB/s]
     downloading nasa_archive.torrent: 100%|█████████████████| 2.01k/2.01k [00:00<00:00, 3.54MiB/s]
     downloading nasa_files.xml: 2.56kiB [00:00, 4.64MiB/s]
     downloading nasa_itemimage.jpg: 100%|███████████████████| 37.5k/37.5k [00:00<00:00, 26.7MiB/s]
     downloading nasa_meta.sqlite: 100%|█████████████████████| 8.00k/8.00k [00:00<00:00, 7.56MiB/s]
     downloading nasa_meta.xml: 7.64kiB [00:00, 18.9MiB/s]
     downloading nasa_reviews.xml: 879iB [00:00, 850kiB/s]

By default, the :func:`download <internetarchive.download>` function sets the ``mtime`` for downloaded files to the ``mtime`` of the file on archive.org. If we retry downloading the same set of files we downloaded above, no requests will be made. This is because the filename, mtime and size of the local files match the filename, mtime and size of the files on archive.org, so we assume that the file has already been downloaded. For example::

    >>> download('nasa', verbose=True)
    nasa:
     skipping nasa/__ia_thumb.jpg, file already exists based on length and date.
     skipping nasa/globe_west_540.jpg, file already exists based on length and date.
     skipping nasa/globe_west_540_thumb.jpg, file already exists based on length and date.
     skipping nasa/nasa_archive.torrent, file already exists based on length and date.
     skipping nasa/nasa_files.xml, file already exists based on length and date.
     skipping nasa/nasa_itemimage.jpg, file already exists based on length and date.
     skipping nasa/nasa_meta.sqlite, file already exists based on length and date.
     skipping nasa/nasa_meta.xml, file already exists based on length and date.
     skipping nasa/nasa_reviews.xml, file already exists based on length and date.

Alternatively, you can skip files based on md5 checksums. This is will take longer because checksums will need to be calculated for every file already downloaded, but will be safer::

    >>> download('nasa', verbose=True, checksum=True)
    nasa:
     skipping nasa/__ia_thumb.jpg, file already exists based on checksum.
     skipping nasa/globe_west_540.jpg, file already exists based on checksum.
     skipping nasa/globe_west_540_thumb.jpg, file already exists based on checksum.
     skipping nasa/nasa_archive.torrent, file already exists based on checksum.
     downloading nasa_files.xml: 2.56kiB [00:00, 5.76MiB/s]
     skipping nasa/nasa_itemimage.jpg, file already exists based on checksum.
     skipping nasa/nasa_meta.sqlite, file already exists based on checksum.
     skipping nasa/nasa_meta.xml, file already exists based on checksum.
     skipping nasa/nasa_reviews.xml, file already exists based on checksum.

By default, the :func:`download <internetarchive.download>` function will download all of the files in an item. However, there are a couple parameters that can be used to download only specific files. Files can be filtered using the ``glob_pattern`` parameter::

    >>> download('nasa', verbose=True, glob_pattern='*xml')
    nasa:
     downloading nasa_files.xml: 2.56kiB [00:00, 1.92MiB/s]
     downloading nasa_meta.xml: 7.64kiB [00:00, 19.7MiB/s]
     downloading nasa_reviews.xml: 879iB [00:00, 832kiB/s]

Files can also be filtered using the ``formats`` parameter. ``formats`` can either be a single format provided as a string::

    >>> download('goodytwoshoes00newyiala', verbose=True, formats='MARC')
    goodytwoshoes00newyiala:
     downloading goodytwoshoes00newyiala_marc.xml: 3.04kiB [00:00, 6.60MiB/s]

Or, a list of formats::

    >>> download('goodytwoshoes00newyiala', verbose=True, formats=['DjVuTXT', 'MARC'])
    goodytwoshoes00newyiala:
     downloading goodytwoshoes00newyiala_djvu.txt: 12.6kiB [00:00, 19.1MiB/s]
     downloading goodytwoshoes00newyiala_marc.xml: 3.04kiB [00:00, 6.33MiB/s]


Downloading On-The-Fly Files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some files on archive.org are generated on-the-fly as requested. This currently includes non-original files of the formats EPUB, MOBI, DAISY, and archive.org's own MARCXML. These files can be downloaded using the ``on_the_fly`` parameter::

    >>> download('wonderfulwizardo00baumiala', verbose=True, formats='DAISY', on_the_fly=True)
    wonderfulwizardo00baumiala:
     downloading wonderfulwizardo00baumiala_daisy.zip: 100%|████| 153k/153k [00:00<00:00, 563kiB/s]


Searching
---------

The :func:`search_items <internetarchive.search_items>` function can be used to iterate through archive.org search results::

    >>> from internetarchive import search_items
    >>> for i in search_items('identifier:nasa'):
    ...     print(i['identifier'])
    ...
    nasa

:func:`search_items <internetarchive.search_items>` can also yield :class:`Item <internetarchive.Item>` objects::

    >>> from internetarchive import search_items
    >>> for item in search_items('identifier:nasa').iter_as_items():
    ...     print(item)
    ...
    Collection(identifier='nasa', exists=True)

:func:`search_items <internetarchive.search_items>` will automatically paginate through large result sets.
