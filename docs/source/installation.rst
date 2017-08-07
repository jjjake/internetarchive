.. _install:

Installation
============


System-Wide Installation
------------------------

Installing the ``internetarchive`` library globally on your system can be done with `pip <http://www.pip-installer.org/>`_.
This is the recommended method for installing ``internetarchive`` (`see below <installation.html#installing-pip>`_ for details on installing pip)::
    
    $ sudo pip install internetarchive

or, with `easy_install <http://pypi.python.org/pypi/setuptools>`_::

    $ sudo easy_install internetarchive

Either of these commands will install the ``internetarchive`` Python library and ``ia`` command-line tool on your system.

**Note**: Some versions of Mac OS X come with Python libraries that are required by ``internetarchive`` (e.g. the Python package ``six``).
This can cause installation issues. If your installation is failing with a message that looks something like::

    OSError: [Errno 1] Operation not permitted: '/var/folders/bk/3wx7qs8d0x79tqbmcdmsk1040000gp/T/pip-TGyjVo-uninstall/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python/six-1.4.1-py2.7.egg-info'

You can use the ``--ignore-installed`` parameter in ``pip`` to ignore the libraries that are already installed, and continue with the rest of the installation::

    $ sudo pip install --ignore-installed internetarchive

More details on this issue can be found here: https://github.com/pypa/pip/issues/3165

Installing Pip
~~~~~~~~~~~~~~

The easiest way to install ``pip`` is probably using your operating systems package manager.

Mac OS, with `homebrew <https://brew.sh/>`_::

    $ brew install pip

Ubuntu, with `apt-get <https://help.ubuntu.com/community/AptGet/Howto>`_::

    $ sudo apt-get install python-pip

If your OS doesn't have a package manager, you can also `install pip with get-pip.py <https://pip.pypa.io/en/stable/installing/>`_::

    $ curl -LOs https://bootstrap.pypa.io/get-pip.py
    $ python get-pip.py


virtualenv
----------

If you don't want to, or can't, install the package system-wide you can use ``virtualenv`` to create an isolated Python environment.

First, make sure ``virtualenv`` is installed on your system. If it's not, you can do so with pip::

    $ sudo pip install virtualenv

With ``easy_install``::

    $ sudo easy_install virtualenv

Or your systems package manager, ``apt-get`` for example::

    $ sudo apt-get install python-virtualenv

Once you have ``virtualenv`` installed on your system, create a virtualenv::

    $ mkdir myproject
    $ cd myproject
    $ virtualenv venv
    New python executable in venv/bin/python
    Installing setuptools, pip............done.

Activate your virtualenv::

    $ . venv/bin/activate

Install ``internetarchive`` into your virtualenv::

    $ pip install internetarchive

Snap
----

You can install the latest `ia` [snap](https://snapcraft.io), and help testing the most recent changes of the master branch in [all the supported Linux distros](https://snapcraft.io/docs/core/install) with:

    $ sudo snap install ia --edge

Every time a new version of `ia` is pushed to the store, you will get it updated automatically.

Binaries
--------

Binaries are also available for the ``ia`` command-line tool::

    $ curl -LOs https://archive.org/download/ia-pex/ia
    $ chmod +x ia

Binaries are generated with `PEX <https://github.com/pantsbuild/pex>`_. The only requirement for using the binaries is that you have Python installed on a Unix-like operating system.

For more details on the command-line interface please refer to the `README <https://github.com/jjjake/internetarchive/blob/master/README.rst>`_, or ``ia help``.


Get the Code
------------

Internetarchive is `actively developed on GitHub <https://github.com/jjjake/internetarchive>`_.

You can either clone the public repository::

    $ git clone git://github.com/jjjake/internetarchive.git

Download the `tarball <https://github.com/jjjake/internetarchive/tarball/master>`_::

    $ curl -OL https://github.com/jjjake/internetarchive/tarball/master

Or, download the `zipball <https://github.com/jjjake/internetarchive/zipball/master>`_::

    $ curl -OL https://github.com/jjjake/internetarchive/zipball/master

Once you have a copy of the source, you can install it into your site-packages easily::

    $ python setup.py install
