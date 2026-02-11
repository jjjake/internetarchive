.. _modules:

Module Documentation
====================

This section contains complete reference documentation for all modules, classes, and methods in the ``internetarchive`` package. For a gentler introduction with examples, see :ref:`python-lib`.

Core Modules
------------

These modules provide the main functionality for interacting with archive.org.

.. _api-module:

internetarchive.api module
~~~~~~~~~~~~~~~~~~~~~~~~~~

The convenience module providing simple functions for common tasks.

.. automodule:: internetarchive.api
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. _session-module:

internetarchive.session module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The session management module for persisting configuration and connections.

.. automodule:: internetarchive.session
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. _item-module:

internetarchive.item module
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modules for working with archive.org items and collections.

.. automodule:: internetarchive.item
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. _account-module:

internetarchive.account module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Module for managing an archive.org account (requires admin privileges).

.. automodule:: internetarchive.account
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. _search-module:

internetarchive.search module
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modules for searching and retrieving items from archive.org.

.. automodule:: internetarchive.search
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

File Operations
---------------

Modules for working with files and specific file operations.

.. automodule:: internetarchive.files
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

Request Handling
----------------

Modules for making HTTP requests to archive.org services.

.. automodule:: internetarchive.iarequest
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

Task and Catalog Management
---------------------------

Modules for working with archive.org tasks and the catalog system.

.. automodule:: internetarchive.catalog
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. _batch-modules:

Batch Operations
----------------

Modules for concurrent batch operations with job logging, multi-disk
routing, and graceful shutdown.

.. automodule:: internetarchive.bulk
   :members:
   :undoc-members:
   :show-inheritance:
   :noindex:

.. automodule:: internetarchive.bulk.engine
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. automodule:: internetarchive.bulk.joblog
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. automodule:: internetarchive.bulk.worker
   :members:
   :undoc-members:
   :show-inheritance:
   :noindex:

.. automodule:: internetarchive.bulk.disk
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. automodule:: internetarchive.bulk.ui
   :members:
   :undoc-members:
   :show-inheritance:
   :noindex:

Workers
~~~~~~~

.. automodule:: internetarchive.workers.download
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

Authentication and Configuration
--------------------------------

Modules for authentication, configuration, and utility functions.

.. automodule:: internetarchive.auth
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. automodule:: internetarchive.config
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

Utility and Supporting Modules
------------------------------

Internal utilities and supporting modules.

.. automodule:: internetarchive.utils
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

.. automodule:: internetarchive.exceptions
   :members:
   :undoc-members:
   :show-inheritance:
   :noindex:

CLI Modules (Internal)
----------------------

.. note::
   These modules are primarily used by the command-line interface and are considered
   internal to the package. For using the CLI, see :ref:`cli`.

.. automodule:: internetarchive.cli
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :noindex:

Complete Package Reference
--------------------------

For a complete listing of all modules and classes:

.. automodule:: internetarchive
   :members:
   :undoc-members:
   :show-inheritance:
   :noindex:
