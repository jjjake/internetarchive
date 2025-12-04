.. _installation:

Installation
============

Recommended: Installing the ``ia`` CLI with ``pipx``
----------------------------------------------------

If your primary goal is to use the **``ia`` command-line tool**, the recommended approach is to install it with ``pipx``. This keeps the CLI isolated from your system Python while making the ``ia`` command available globally.

Using ``pipx`` ensures the CLI is isolated, easy to upgrade, and globally accessible.

*If you just want to try out the ``ia`` CLI without installing anything, you can use the prebuilt binary instead. See the :ref:`binaries` section below for details.*

**Prerequisite:** Make sure you have ``pipx`` installed. For installation instructions, see the `pipx installation guide <https://pipx.pypa.io/stable/installation/>`_.

1. **Install ``internetarchive`` using ``pipx``**:

.. code-block:: console

    pipx install internetarchive

2. **Verify the installation**:

.. code-block:: console

    ia --version

   This should display the installed version of the ``ia`` CLI.

Troubleshooting ``pipx`` Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Permission errors**: Avoid using ``sudo`` with ``pipx``. It is designed to work without elevated permissions.
- **Command not found**: If ``ia`` is not recognized, restart your terminal or run:

.. code-block:: console

    pipx ensurepath

- **Python version issues**: Ensure you are using Python 3.9 or later.

For more details, refer to the `pipx documentation <https://pipx.pypa.io/stable/>`_.

Installing for Python Scripts (using a virtual environment)
-----------------------------------------------------------

If you want to import ``internetarchive`` in your Python scripts (for programmatic access), the recommended approach is to use a virtual environment:

.. code-block:: console

    python -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install internetarchive

After this, you can use the library in Python:

.. code-block:: python

    from internetarchive import get_item

    item = get_item("nasa")
    print(item.metadata)

.. _binaries:

Using ``ia`` Binaries
---------------------

The easiest way to start using ``ia`` is downloading a binary.
The only requirements of the binary are a Unix-like environment with Python installed.
To download the latest binary, and make it executable simply run the following commands:

.. code-block:: console

    curl -LOs https://archive.org/download/ia-pex/ia
    chmod +x ia

Binaries are generated with `PEX <https://github.com/pantsbuild/pex>`_. The only requirement for using the binaries is that you have a `supported version of Python <https://devguide.python.org/versions/>`_ installed on a Unix-like operating system.

For more details on the command-line interface please refer to the `README <https://github.com/jjjake/internetarchive/blob/master/README.rst>`_, or run ``ia help``.

.. _updating:

Updating
--------

The method for updating depends on how you originally installed:

**If you installed** ``ia`` **with pipx** (CLI):

.. code-block:: console

      pipx upgrade internetarchive

**If you installed** ``internetarchive`` **in a virtual environment (Python library)**:
   Activate your virtual environment, then:

   .. code-block:: console

      pip install --upgrade internetarchive

**If you are using the binary**:
   Simply download the latest binary again with the same steps as above:

.. code-block:: console

      curl -LOs https://archive.org/download/ia-pex/ia
      chmod +x ia

For more information about recent changes, see :ref:`updates`.
