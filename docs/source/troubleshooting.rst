.. _troubleshooting:

Troubleshooting
===============

HTTPS Issues
------------

The ``internetarchive`` library uses the HTTPS protocol for making secure requests by default.
This can cause issues when using versions of Python earlier than 2.7.9:

    Certain Python platforms (specifically, versions of Python earlier than 2.7.9) have restrictions in their ssl module that limit the configuration that urllib3 can apply.
    In particular, this can cause HTTPS requests that would succeed on more featureful platforms to fail, and can cause certain security features to be unavailable.

See `https://urllib3.readthedocs.org/en/latest/security.html <https://urllib3.readthedocs.org/en/latest/security.html>`_ for more details.

If you are using a Python version earlier than 2.7.9, you might see ``InsecurePlatformWarning`` and ``SNIMissingWarning`` warnings and your reqeusts might fail. There are a few options to address this issue:

    1. Upgrade your Python to version 2.7.9 or more recent.
    2. Install or upgrade the following Python modules as `documented here <https://urllib3.readthedocs.org/en/latest/security.html#installing-urllib3-with-sni-support-and-certificates>`_: ``PyOpenSSL``, ``ndg-httpsclient``, and ``pyasn1``.
    3. Use HTTP to make insecure requests in one of the following ways:
           + Adding the following lines to your ``ia.ini`` config file (usually located at ``~/.config/ia.ini`` or ``~/.ia.ini``):
               .. code:: bash

                 [general]
                 secure = false

           + In the Python interface, using a config dict:

               .. code:: python

                 >>> from internetarchive import get_item
                 >>> config = dict(general=dict(secure=False))
                 >>> item = get_item('<identifier>', config=config)

           + In the command-line interface, use the ``--insecure`` option:

               .. code:: bash

                 $ ia --insecure download <identifier>
