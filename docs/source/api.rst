.. _api:

Developer Interface
===================

.. module:: internetarchive

Configuration
-------------

Certain functions of the internetarchive library require your Archive.org credentials (i.e. uploading, modifying metadata, searching).
Your credentials and other configurations can be provided via a dictionary when insantiating an :class:`ArchiveSession` or :class:`Item` object, or in a config file.

The easiest way to create a config file is with the `configure <internetarchive.html#internetarchive.configure>`_ function::

    >>> from internetarchive import configure
    >>> configure('user@example.com', 'password')

Config files are stored in either ``$HOME/.ia`` or ``$HOME/.config/ia.ini`` by default, but other config files can be specified when insantiating an :class:`ArchiveSession` or :class:`Item` object.

IA-S3 Configuration
~~~~~~~~~~~~~~~~~~~

Your IA-S3 keys are required for uploading and modifying metadata.
You can retrieve your IA-S3 keys at https://archive.org/account/s3.php.

They can be specified in your config file like so::

    [s3]
    access = mYaccEsSkEY
    secret = mYs3cREtKEy

Or, using the :class:`ArchiveSession` obect::

    >>> from internetarchive import get_session
    >>> c = {'s3': {'access': 'mYaccEsSkEY', 'secret': 'mYs3cREtKEy'}}
    >>> s = get_session(config=c)
    >>> s.access_key
    'mYaccEsSkEY'

Cookie Confgiuration
~~~~~~~~~~~~~~~~~~~~

Your Archive.org logged-in cookies are required for downloading access-restricted files that you have permissions to and retrieving information about Archive.org catalog tasks.

Your cookies can be specified like so::

    [cookies]
    logged-in-user = user%40example.com
    logged-in-sig = <redacted>

Or, using the :class:`ArchiveSession` obect::

    >>> from internetarchive import get_session
    >>> c = {'cookies': {'logged-in-user': 'user%40example.com', 'logged-in-sig': 'foo'}}
    >>> s = get_session(config=c)
    >>> s.cookies['logged-in-user']
    'user%40example.com'


Logging Configuration
~~~~~~~~~~~~~~~~~~~~~

You can specify logging levels and the location of your log file like so::

    [logging]
    level = INFO
    file = /tmp/ia.log

Or, using the :class:`ArchiveSession` obect::

    >>> from internetarchive import get_session
    >>> c = {'logging': {'level': 'INFO', 'file': '/tmp/ia.log'}}
    >>> s = get_session(config=c)

By default logging is turned off.

Other Configuration
~~~~~~~~~~~~~~~~~~~

By default all requests are HTTPS in Python versions 2.7.10 or newer.
You can change this setting in your config file in the ``general`` section::

    [general]
    secure = False

Or, using the :class:`ArchiveSession` obect::

    >>> from internetarchive import get_session
    >>> s = get_session(config={'general': {'secure': False}})

In the example above, all requests will be made via HTTP.


ArchiveSession Objects
----------------------
The ArchiveSession object is subclassed from :class:`requests.Session`.
It collects together your credentials and config.

.. autofunction:: get_session


Item Objects
------------

:class:`Item` objects represent `Internet Archive items <https://blog.archive.org/2011/03/31/how-archive-org-items-are-structured/>`_.
From the :class:`Item` object you can create new items, upload files to existing items, read and write metadata, and download or delete files.

.. autofunction:: get_item

Uploading
~~~~~~~~~

Uploading to an item can be done using :meth:`Item.upload`::

    >>> item = get_item('my_item')
    >>> r = item.upload('/home/user/foo.txt')

Or :func:`internetarchive.upload`::

    >>> from internetarchive import upload
    >>> r = upload('my_item', '/home/user/foo.txt')

The item will automatically be created if it does not exist.

Refer to `Archive.org Identifiers <metadata.html#archive-org-identifiers>`_ for more information on creating valid Archive.org identifiers.

Setting Remote Filenames
^^^^^^^^^^^^^^^^^^^^^^^^

Remote filenames can be defined using a dictionary::

    >>> from io import BytesIO
    >>> fh = BytesIO()
    >>> fh.write(b'foo bar')
    >>> item.upload({'my-remote-filename.txt': fh})


.. autofunction:: upload

Metadata
~~~~~~~~

.. autofunction:: modify_metadata

The default target to write to is ``metadata``.
If you would like to write to another target, such as ``files``, you can specify so using the ``target`` parameter.
For example, if we had an item whose identifier was ``my_identifier`` and you wanted to add a metadata field to a file within the item called foo.txt::

    >>> r = modify_metadata('my_identifier', metadata=dict(title='My File'), target='files/foo.txt')
    >>> from internetarchive import get_files
    >>> f = list(get_files('iacli-test-item301', 'foo.txt'))[0]
    >>> f.title
    'My File'

You can also create new targets if they don’t exist::

    >>> r = modify_metadata('my_identifier', metadata=dict(foo='bar'), target='extra_metadata')
    >>> from internetarchive import get_item
    >>> item = get_item('my_identifier')
    >>> item.item_metadata['extra_metadata']
    {'foo': 'bar'}


Downloading
~~~~~~~~~~~

.. autofunction:: download


Deleting
~~~~~~~~

.. autofunction:: delete


File Objects
~~~~~~~~~~~~

.. autofunction:: get_files


Searching Items
---------------


.. autofunction:: search_items


Internet Archive Tasks
----------------------
.. autofunction:: get_tasks
