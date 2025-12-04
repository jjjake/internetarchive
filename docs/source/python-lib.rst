.. _python-lib:

Python Library Usage
====================

The ``internetarchive`` Python library provides two main ways to interact with archive.org:

1. **Simple functional interface** via :mod:`internetarchive.api` - Easy to use for common tasks
2. **Flexible object-oriented interface** via :class:`~internetarchive.session.ArchiveSession` - More control for complex applications

Quick Start
-----------

The easiest way to get started is with the :mod:`internetarchive.api` module, which provides
simple functions for common operations:

.. code-block:: python

    from internetarchive import download, upload, search_items, get_item

    # Download files from an item
    download('TripDown1905', glob_pattern='*.mp4')

    # Search for items
    search = search_items('collection:opensource')
    for result in search:
        print(result['identifier'])

    # Get an item and work with it
    item = get_item('TripDown1905')
    print(item.metadata['title'])

For more control and to persist configuration across operations, use a :class:`~internetarchive.session.ArchiveSession`:

.. code-block:: python

    from internetarchive import get_session

    # Create a session with your configuration
    session = get_session(config_file='~/.config/ia.ini')

    # Use the session for all operations
    item = session.get_item('TripDown1905')
    item.download()
    search = session.search_items('subject:science')

Simple Functional Interface
---------------------------

The :mod:`internetarchive.api` module provides these convenient functions for common tasks:

.. automodule:: internetarchive.api
   :members:
   :exclude-members: get_username, get_user_info, configure
   :noindex:

These functions are great for scripts and simple applications. They automatically create
a session in the background for you. For complete documentation including all parameters,
see :ref:`api-module` in the reference.

Using Sessions
--------------

For more complex applications or when you need to perform multiple operations, use
the :class:`~internetarchive.session.ArchiveSession` class:

.. autoclass:: internetarchive.session.ArchiveSession
   :members:
   :exclude-members: set_file_logger, set_stream_logger, rebuild_auth,
                     mount_http_adapter, send, _get_user_agent_string,
                     s3_is_overloaded, get_tasks_api_rate_limit
   :noindex:

Creating a session:

.. code-block:: python

    from internetarchive import get_session

    # From config file
    session = get_session(config_file='~/.config/ia.ini')

    # From dictionary
    config = {
        's3': {
            'access': 'your_access_key',
            'secret': 'your_secret_key'
        }
    }
    session = get_session(config=config)

For complete session documentation, see :ref:`session-module`.

Working with Items
------------------

Once you have an item (from :func:`get_item` or :meth:`~internetarchive.session.ArchiveSession.get_item`), you can:

.. code-block:: python

    item = get_item('TripDown1905')

    # Access metadata
    print(item.metadata['title'])
    print(item.metadata['creator'])

    # Download files
    item.download(glob_pattern='*.mp4')

    # Upload new files
    item.upload(['file1.txt', 'file2.jpg'],
                metadata={'title': 'My New Files'})

    # Modify metadata
    item.modify_metadata({'subject': ['history', 'film']})

    # List files
    for file in item.files:
        print(file.name, file.format)

For complete item documentation, see :ref:`item-module`.

Searching for Items
-------------------

.. code-block:: python

    from internetarchive import search_items

    # Basic search
    search = search_items('collection:opensource movies')

    # Iterate through results
    for result in search:
        print(f"{result['identifier']}: {result.get('title', 'No title')}")

    # Get specific fields
    search = search_items('subject:science',
                          fields=['identifier', 'title', 'date'])
    for result in search:
        print(result)

For complete search documentation, see :ref:`search-module`.

Common Patterns
---------------

**Download all files from multiple items:**

.. code-block:: python

    from internetarchive import get_item

    identifiers = ['TripDown1905', 'goodytwoshoes00newyiala']
    for identifier in identifiers:
        item = get_item(identifier)
        item.download()

**Upload with custom metadata:**

.. code-block:: python

    from internetarchive import upload

    upload(
        'my-new-item-001',
        files=['document.pdf', 'cover.jpg'],
        metadata={
            'title': 'My Document',
            'mediatype': 'texts',
            'collection': 'opensource',
            'subject': ['documentation', 'tutorial']
        }
    )

**Search and process results:**

.. code-block:: python

    from internetarchive import search_items

    # Search with pagination
    search = search_items(
        'collection:prelinger',
        params={'rows': 50, 'page': 1}
    )

    # Collect identifiers
    identifiers = [result['identifier'] for result in search]

    # Process in batches
    for identifier in identifiers[:10]:  # First 10 items
        print(f"Processing {identifier}")

Configuration
-------------

The library needs your archive.org credentials for certain operations (uploading,
modifying metadata, etc.). You can configure it in several ways:

1. **Config file** (recommended): Use ``ia configure`` from the CLI or :func:`~internetarchive.api.configure` from Python
2. **Environment variables**: Set ``IA_ACCESS_KEY_ID`` and ``IA_SECRET_ACCESS_KEY``
3. **Python dictionary**: Pass credentials directly when creating a session

See :ref:`configuration` for complete configuration details.

Next Steps
----------

For complete documentation of all modules, classes, and methods, see :ref:`modules`.

For troubleshooting and advanced usage, check the examples in the
`GitHub repository <https://github.com/jjjake/internetarchive>`_.
