A Python and Command-Line Interface to Archive.org
==================================================

|tox|
|versions|
|downloads|
|contributors|

.. |tox| image:: https://github.com/jjjake/internetarchive/actions/workflows/tox.yml/badge.svg
    :target: https://github.com/jjjake/internetarchive/actions/workflows/tox.yml

.. |versions| image:: https://img.shields.io/pypi/pyversions/internetarchive.svg
    :target: https://pypi.org/project/internetarchive

.. |downloads| image:: https://static.pepy.tech/badge/internetarchive/month
    :target: https://pepy.tech/project/internetarchive

.. |contributors| image:: https://img.shields.io/github/contributors/jjjake/internetarchive.svg
    :target: https://github.com/jjjake/internetarchive/graphs/contributors

This package installs a command-line tool named ``ia`` for using Archive.org from the command-line.
It also installs the ``internetarchive`` Python module for programmatic access to archive.org.
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
