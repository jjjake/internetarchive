.. _quickstart:

Quickstart
==========


Configuring
-----------

Certain functionality of the internetarchive Python library requires your Archive.org credentials.
Your `IA-S3 keys <https://archive.org/account/s3.php>`_ are required for uploading and modifying metadata, and your Archive.org logged-in cookies are required for downloading access-restricted content and viewing your task history.
To automatically create a config file with your Archive.org credentials, you can use the ``ia`` command-line tool::

    $ ia configure
    Enter your Archive.org credentials below to configure 'ia'.
    
    Email address: user@example.com
    Password:
    
    Config saved to: /home/user/.config/ia.ini

Your config file will be saved to ``$HOME/.config/ia.ini``, or ``$HOME/.ia`` if you do not have a ``.config`` directory in ``$HOME``.


Uploading
---------

Creating a new `item on Archive.org <https://blog.archive.org/2011/03/31/how-archive-org-items-are-structured/>`_ and uploading files to it is as easy as::

    >>> from internetarchive import upload
    >>> md = dict(collection='test_collection', title='My New Item', mediatype='movies')
    >>> r = upload('<identifier>', files=['foo.txt', 'bar.mov'], metadata=md)
    >>> r[0].status_code
    200

You can set remote filename using a dictionary::

    >>> r = upload('<identifier>', files={'remote-name.txt': 'local-name.txt'})

You can upload file-like objects::

    >>> r = upload('iacli-test-item301', {'foo.txt': StringIO(u'bar baz boo')})

If the item already has a file with the same filename, the existing file within the item will be overwritten.

:func:`upload <internetarchive.upload>` can also upload directories. For example, the following command will upload ``my_dir`` and all of it's contents to ``https://archive.org/download/my_item/my_dir/``::

    >>> r = upload('my_item', 'my_dir')

To upload only the contents of the directory, but not the directory itself, simply append a slash to your directory::

    >>> r = upload('my_item', 'my_dir/')

This will upload all of the contents of ``my_dir`` to ``https://archive.org/download/my_item/``. :func:`upload <internetarchive.upload>` accepts relative or absolute paths.

**Note**: metadata can only be added to an item using the :func:`upload <internetarchive.upload>` function on item creation. If an item already exists and you would like to modify it's metadata, you must use :func:`modify_metadata <internetarchive.modify_metadata>`.


Metadata
--------

Reading Metadata
^^^^^^^^^^^^^^^^

You can access all of an item's metadata via the :class:`Item <internetarchive.Item>` object::

    >>> from internetarchive import get_item
    >>> item = get_item('iacli-test-item301')
    >>> item.item_metadata['metadata']['title']
    'My Title'

:func:`get_item <internetarchive.get_item>` retrieves all of an item's metadata via the `Internet Archive Metadata API <http://blog.archive.org/2013/07/04/metadata-api/>`_. This metadata can be accessed via the ``Item.item_metadata`` attribute::
    
    >>> item.item_metadata.keys()
    dict_keys(['created', 'updated', 'd2', 'uniq', 'metadata', 'item_size', 'dir', 'd1', 'files', 'server', 'files_count', 'workable_servers'])

All of the top-level keys in ``item.item_metadata`` are available as attributes::

    >>> item.server
    'ia801507.us.archive.org'
    >>> item.item_size
    161752024
    >>> item.files[0].name
    'blank.txt'
    >>> item.metadata['identifier']
    'iacli-test-item301'


Writing Metadata
^^^^^^^^^^^^^^^^

Adding new metadata to an item can be done using the :func:`modify_metadata <internetarchive.modify_metadata>` function::

    >>> from internetarchive import modify_metadata
    >>> r = modify_metadata('<identifier>', metadata=dict(title='My Stuff'))
    >>> r.status_code
    200

Modifying metadata can also be done via the :class:`Item <internetarchive.Item>` object. For example, changing the title we set in the example above can be done like so::
    
    >>> r = item.modify_metadata(dict(title='My New Title'))
    >>> item.metadata['title']
    'My New Title'

To remove a metadata field from an item's metadata, set the value to ``'REMOVE_TAG'``::

    >>> r = item.modify_metadata(dict(foo='new metadata field.'))
    >>> item.metadata['foo']
    'new metadata field.'
    >>> r = item.modify_metadata(dict(title='REMOVE_TAG'))
    >>> print(item.metadata.get('foo'))
    None

The default behaviour of :func:`modify_metadata <internetarchive.modify_metadata>` is to modify item-level metadata (i.e. title, description, etc.). If we want to modify different kinds of metadata, say the metadata of a specific file, we have to change the metadata ``target`` in the call to :func:`modify_metadata <internetarchive.modify_metadata>`::

    >>> r = item.modify_metadata(dict(title='My File Title'), target='files/foo.txt')
    >>> f = item.get_file('foo.txt')
    >>> f.title
    'My File Title'

Refer to `Internet Archive Metadata <metadata.html>`_ for more specific details regarding metadata and Archive.org.


Downloading
-----------

Downloading files can be done via the :func:`download <internetarchive.download>` function::

    >>> from internetarchive import download
    >>> download('nasa', verbose=True)
    nasa:
     downloaded nasa/globe_west_540.jpg to nasa/globe_west_540.jpg
     downloaded nasa/NASAarchiveLogo.jpg to nasa/NASAarchiveLogo.jpg
     downloaded nasa/globe_west_540_thumb.jpg to nasa/globe_west_540_thumb.jpg
     downloaded nasa/nasa_reviews.xml to nasa/nasa_reviews.xml
     downloaded nasa/nasa_meta.xml to nasa/nasa_meta.xml
     downloaded nasa/nasa_archive.torrent to nasa/nasa_archive.torrent
     downloaded nasa/nasa_files.xml to nasa/nasa_files.xml

By default, the :func:`download <internetarchive.download>` function sets the ``mtime`` for downloaded files to the ``mtime`` of the file on Archive.org. If we retry downloading the same set of files we downloaded above, no requests will be made. This is because the filename, mtime and size of the local files match the filename, mtime and size of the files on Archive.org, so we assume that the file has already been downloaded. For example::

    >>> download('nasa', verbose=True)
    nasa:
     skipping nasa/globe_west_540.jpg, file already exists based on length and date.
     skipping nasa/NASAarchiveLogo.jpg, file already exists based on length and date.
     skipping nasa/globe_west_540_thumb.jpg, file already exists based on length and date.
     skipping nasa/nasa_reviews.xml, file already exists based on length and date.
     skipping nasa/nasa_meta.xml, file already exists based on length and date.
     skipping nasa/nasa_archive.torrent, file already exists based on length and date.
     skipping nasa/nasa_files.xml, file already exists based on length and date.

Alternatively, you can skip files based on md5 checksums. This is will take longer because checksums will need to be calculated for every file already downloaded, but will be safer::

    >>> download('nasa', verbose=True, checksum=True)
    nasa:
     skipping nasa/globe_west_540.jpg, file already exists based on checksum.
     skipping nasa/NASAarchiveLogo.jpg, file already exists based on checksum.
     skipping nasa/globe_west_540_thumb.jpg, file already exists based on checksum.
     skipping nasa/nasa_reviews.xml, file already exists based on checksum.
     skipping nasa/nasa_meta.xml, file already exists based on checksum.
     skipping nasa/nasa_archive.torrent, file already exists based on checksum.
     skipping nasa/nasa_files.xml, file already exists based on length and date.

By default, the :func:`download <internetarchive.download>` function will download all of the files in an item. However, there are a couple parameters that can be used to download only specific files. Files can be filtered using the ``glob_pattern`` parameter::

    >>> download('nasa', verbose=True, glob_pattern='*xml')
    nasa:
     downloaded nasa/nasa_reviews.xml to nasa/nasa_reviews.xml
     downloaded nasa/nasa_meta.xml to nasa/nasa_meta.xml
     downloaded nasa/nasa_files.xml to nasa/nasa_files.xml

Files can also be filtered using the ``formats`` parameter. ``formats`` can either be a single format provided as a string::

    >>> download('goodytwoshoes00newyiala', verbose=True, formats='EPUB')
    goodytwoshoes00newyiala:
     downloaded goodytwoshoes00newyiala/goodytwoshoes00newyiala.epub to goodytwoshoes00newyiala/goodytwoshoes00newyiala.epub

Or, a list of formats::
    
    >>> download('goodytwoshoes00newyiala', verbose=True, formats=['EPUB', 'MARC'])
    goodytwoshoes00newyiala:
     downloaded goodytwoshoes00newyiala/goodytwoshoes00newyiala_meta.mrc to goodytwoshoes00newyiala/goodytwoshoes00newyiala_meta.mrc
     downloaded goodytwoshoes00newyiala/goodytwoshoes00newyiala.epub to goodytwoshoes00newyiala/goodytwoshoes00newyiala.epub


Searching
---------

The :func:`search_items <internetarchive.search_items>` function can be used to iterate through Archive.org search results::

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
