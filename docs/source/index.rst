The Internet Archive Python Library
===================================

Release v\ |version|. (:ref:`Installation <installation>`)

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

Welcome to the documentation for the ``internetarchive`` Python library. This tool provides both a **command-line interface (CLI)** and a **Python API** for interacting with **archive.org**, allowing you to search, download, upload and interact with archive.org services from your terminal or in Python.

These docs guide you through installation, usage, and examples, whether you’re new to Python, just want to try the CLI, or are building applications that work with the Internet Archive. Please report any issues or contribute on `GitHub <https://github.com/jjjake/internetarchive>`_.


Quick start
===========

If you're new to Python or the command line interface (CLI), the easiest way to get started is to follow these three steps:

1. :ref:`Download a binary <binaries>` of the ``ia`` command-line tool
2. :ref:`Configure your environment <configuration>` with your Archive.org credentials
3. :ref:`Visit the CLI documentation <cli>` to start exploring how to use the tool

Documentation
=============

For more detailed information, including installing the command-line tool and Python library, please refer to the following sections:

Setup & Configuration
---------------------

Get the tools running on your system:

.. toctree::
   :maxdepth: 2

   installation
   configuration

User Interfaces
---------------

These are the main ways to use the Internet Archive Python Library and CLI:

.. toctree::
   :maxdepth: 2

   cli
   python-lib

Performance & Scaling
---------------------

Optimize your workflows:

.. toctree::
   :maxdepth: 2

   parallel

Development & Community
-----------------------

Contribute and stay updated:

.. toctree::
   :maxdepth: 2

   contributing
   updates

Help & Support
--------------

Get help when you need it:

.. toctree::
   :maxdepth: 2

   troubleshooting

- **Documentation**: Check this troubleshooting guide first
- **Community**: Search existing `GitHub Issues <https://github.com/jjjake/internetarchive/issues>`_
- **Report**: If you can't find a solution, `open a new issue <https://github.com/jjjake/internetarchive/issues/new>`_

When reporting an issue, please include:

- The exact command or code that caused the problem
- Any error messages you received
- Your operating system and Python version

Before reporting, make sure you're using the latest version of the library and :ref:`updating` if necessary.

Reference
---------

Complete reference documentation for all modules:

.. toctree::
   :maxdepth: 2

   modules

Authors
=======

.. toctree::
   :maxdepth: 2

   authors

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
