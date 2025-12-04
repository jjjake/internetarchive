.. _troubleshooting:

Troubleshooting
===============

HTTPS Issues
------------

The ``internetarchive`` library uses the HTTPS protocol for making secure requests by default.
If you run into problems with this, you can use HTTP to make insecure requests in one of the following ways:

    + Adding the following lines to your ``ia.ini`` config file (usually located at ``~/.config/ia.ini`` or ``~/.ia.ini``):

        .. code:: bash

          [general]
          secure = false

    + In the Python interface, using a config dict:

        .. code:: python

          >>> from internetarchive import get_item
          >>> config = {'general': {'secure': False}}
          >>> item = get_item('<identifier>', config=config)

    + In the command-line interface, use the ``--insecure`` option:

        .. code:: bash

          $ ia --insecure download <identifier>

OverflowError
-------------

On some 32-bit systems you may run into issues uploading files larger than 2 GB.
You may see an error that looks something like ``OverflowError: long int too large to convert to int``.
You can get around this by upgrading ``requests``::

    pip install --upgrade requests

You can find more details about this issue at the following links:

https://github.com/sigmavirus24/requests-toolbelt/issues/80
https://github.com/kennethreitz/requests/issues/2691

Getting Further Help
--------------------

If your issue isn't covered here, please:

1. Search the `existing GitHub Issues <https://github.com/jjjake/internetarchive/issues>`_
   to see if it's already been reported
2. If not, `open a new issue <https://github.com/jjjake/internetarchive/issues/new>`_ with:
   - A clear description of the problem
   - Steps to reproduce
   - Any error messages
   - Your environment (OS, Python version, internetarchive version)

Before reporting, make sure you're using the latest version of the library and :ref:`updating` if necessary.
