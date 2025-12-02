.. _install:

Installation
============

Installing ``internetarchive`` with ``pipx``
--------------------------------------------
The ``internetarchive`` library is a Python tool for interacting with the Internet Archive, allowing you to search, download, and upload files. To make it easy to use, we recommend installing it with ``pipx``, a tool that installs Python applications in isolated environments.

**Note**: If you only need the command-line tool and don’t plan to use the Python library, you can download a binary instead. See the :ref:`binaries` section below for more information.

What is ``pipx``?
~~~~~~~~~~~~~~~~~
``pipx`` is a tool for installing and running Python applications in isolated environments. It ensures that the tools you install don’t interfere with other Python projects or system-wide packages. It’s perfect for CLI tools like ``internetarchive``.

Prerequisites
~~~~~~~~~~~~~
Before installing ``internetarchive``, you’ll need:

1. **Python 3.9 or later**: Python 3.9 is the oldest version still officially supported by the Python development team (as of October 2023). You can check your Python version by running:
   ::

     python --version

   If Python is not installed, download it from `python.org <https://www.python.org/downloads/>`_.
   On MacOS, you can install a `supported version of Python <https://devguide.python.org/versions/>`_ with `Homebrew <https://brew.sh/>`_ (e.g. ``brew install python3``).

2. **`pipx`**: If you don’t have ``pipx`` installed, please refer to the `pipx installation documentation <https://pipx.pypa.io/stable/installation/>`_ for installation instructions.

Installing ``internetarchive``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Once ``pipx`` is installed, you can install ``internetarchive`` with a single command:
::

  pipx install internetarchive

This will download and install the ``internetarchive`` library in an isolated environment, making it available as a command-line tool.

Verifying the Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~
To confirm that ``internetarchive`` is installed correctly, run:
::

  ia --version

If the installation was successful, this will display the version of ``internetarchive``.

Upgrading ``internetarchive``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To upgrade ``internetarchive`` to the latest version, use:
::

  pipx upgrade internetarchive

Uninstalling ``internetarchive``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If you no longer need ``internetarchive``, you can uninstall it with:
::

  pipx uninstall internetarchive

Troubleshooting
~~~~~~~~~~~~~~~
If you encounter any issues:

- **Permission Errors**: Ensure you’re not using ``sudo`` with ``pipx``. It’s designed to work without elevated permissions.
- **Command Not Found**: Restart your terminal after installing ``pipx`` or run ``pipx ensurepath`` again.
- **Python Version Issues**: Ensure you’re using Python 3.9 or later.

For further assistance with ``pipx``, refer to the `pipx documentation <https://pipx.pypa.io/stable/>`_.

.. _binaries:

Binaries
--------

Binaries are also available for the ``ia`` command-line tool::

    $ curl -LOs https://archive.org/download/ia-pex/ia
    $ chmod +x ia

Binaries are generated with `PEX <https://github.com/pantsbuild/pex>`_. The only requirement for using the binaries is that you have a `supported version of Python <https://devguide.python.org/versions/>`_ installed on a Unix-like operating system.

For more details on the command-line interface please refer to the `README <https://github.com/jjjake/internetarchive/blob/master/README.rst>`_, or ``ia help``.
