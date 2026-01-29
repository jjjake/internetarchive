.. _configuration:

Configuration
=============

Certain functionality of the internetarchive Python library requires your archive.org credentials.
Your `IA-S3 keys <https://archive.org/account/s3.php>`_ are required for uploading, searching, and modifying metadata, and your archive.org logged-in cookies are required for downloading access-restricted content and viewing your task history.

Your keys can be saved to a config file or set as environment variables.


Config File
-----------

To automatically create a config file with your archive.org credentials, you can use the ``ia`` command-line tool:

.. code-block:: console

    $ ia configure
    Enter your archive.org credentials below to configure 'ia'.

    Email address: user@example.com
    Password:

    Config saved to: /home/user/.config/ia.ini

Your config file will be saved to ``$HOME/.config/ia.ini``, or ``$HOME/.ia`` if you do not have a ``.config`` directory in ``$HOME``.
Alternatively, you can specify your own path to save the config to via ``ia --config-file '~/.ia-custom-config' configure``.

If you have a netrc file with your archive.org credentials in it, you can simply run ``ia configure --netrc``.

``ia configure`` can be rerun at any time to update your credentials.
Custom configuration options manually added to the config file will be preserved when using ``ia configure``.

*Note: Python's netrc library does not currently support passphrases, or passwords with spaces in them, and therefore are not currently supported here.*

Config File Format
~~~~~~~~~~~~~~~~~~

Below is an example of a config file with the required sections and keys, as well as optional keys for advanced configuration. You should generally only configure with ``ia configure``, but you can manually edit the config file if needed.

.. code-block:: ini

   [s3]
   access = <IA-S3 Access Key>
   secret = <IA-S3 Secret Key>

   [cookies]
   logged-in-user = <logged-in-user Cookie>
   logged-in-sig = <logged-in-sig Cookie>

   [general]
   screenname = <Archive.org Screenname>
   user_agent_suffix = MyApp/1.0
   custom-var = foo

   [custom]
   foo = bar


The config above would generate the following configuration dictionary when loaded via the ``get_session`` function:

.. code-block:: python

    >>> from internetarchive import  get_session
    >>> s = get_session(config_file='/tmp/ia.ini')
    >>> print(s.config)
    {'s3': {
        'access': '<IA-S3 Access Key>',
        'secret': '<IA-S3 Secret Key>'
     },
     'cookies': {
        'logged-in-user': '<logged-in-user Cookie>',
        'logged-in-sig': '<logged-in-sig Cookie>'},
     'general': {
        'screenname': '<Archive.org Screenname>',
        'user_agent_suffix': 'MyApp/1.0',
        'custom-var': 'foo'
     },
     'custom': {
        'foo': 'bar'
     }
    }


Environment Variables
---------------------

Alternatively, you can set the following environment variables with your S3 credentials:

   - ``IA_ACCESS_KEY_ID``: Your IA-S3 access key
   - ``IA_SECRET_ACCESS_KEY``: Your IA-S3 secret key

*Note: Both environment variables must be set together. If only one is set, a* :class:`ValueError` *will be raised. If both are set, they will take precedence over the config file.*


Advanced Configuration Options
------------------------------

User-Agent Suffix
~~~~~~~~~~~~~~~~~

You can customize the User-Agent header sent with requests by setting a suffix that gets appended to the default User-Agent string. This is useful for identifying your application in archive.org server logs.

**Config file:**

.. code-block:: ini

   [general]
   user_agent_suffix = MyApp/1.0

**Python:**

.. code-block:: python

    >>> from internetarchive import get_session
    >>> s = get_session(config={'general': {'user_agent_suffix': 'MyApp/1.0'}})
    >>> print(s.headers['User-Agent'])
    'internetarchive/5.7.2 (Linux x86_64; Python 3.11.4) MyApp/1.0'

**Command-line:**

.. code-block:: console

    $ ia --user-agent-suffix 'MyApp/1.0' metadata nasa

The suffix is appended to the default User-Agent, which includes the library version, platform, and Python version.
