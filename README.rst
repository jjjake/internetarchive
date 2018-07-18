A Python and Command-Line Interface to Archive.org
==================================================

|travis| |snapcraft|

.. |travis| image:: https://travis-ci.org/jjjake/internetarchive.svg
    :target: https://travis-ci.org/jjjake/internetarchive
.. |snapcraft| image:: https://build.snapcraft.io/badge/jjjake/internetarchive.svg
    :target: https://build.snapcraft.io/user/jjjake/internetarchive
    :alt: Snap Status

This package installs a command-line tool named ``ia`` for using Archive.org from the command-line.
It also installs the ``internetarchive`` Python module for programatic access to archive.org.
Please report all bugs and issues on `Github <https://github.com/jjjake/internetarchive/issues>`__.


Installation
------------

You can install this module via pip:

.. code:: bash

    $ pip install internetarchive

Binaries of the command-line tool are also available:

.. code:: bash

    $ curl -LO https://archive.org/download/ia-pex/ia
    $ chmod +x ia
    $ ./ia help


Documentation
-------------

Documentation is available at `https://archive.org/services/docs/api/internetarchive <https://archive.org/services/docs/api/internetarchive>`_.


Contributing
------------

All contributions are welcome and appreciated. Please see `https://archive.org/services/docs/api/internetarchive/contributing.html <https://archive.org/services/docs/api/internetarchive/contributing.html>`_ for more details.
