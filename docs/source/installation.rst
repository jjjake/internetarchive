.. _install:

Installation
============


System-Wide Installation
-------------------------

Installing the ``internetarchive`` library globally on your system can be done with `pip <http://www.pip-installer.org/>`_.
This is the recommended method for installing ``internetarchive`` (`see below <installation.html#installing-pip>`_ for details on installing pip).
If you are on Mac OS X, refer to the `Mac OS X section <installation.html#mac-os-x>`_ below before proceeding.
Once you're ready to install, run the following command::

    $ sudo python3 -m pip install internetarchive

Updating Your $PATH
~~~~~~~~~~~~~~~~~~~

Once you have successfully installed ``internetarchive``, you may need to update your ``$PATH`` (e.g. if running ``ia`` in your terminal returns an error).
If you receive a command not found error, run the following command to update your ``$PATH``::

    $ echo "$(python3 -m site --user-base)/bin" | sudo tee -a /etc/paths

Updating ia
~~~~~~~~~~~

To update, you can run the following command::

    $  sudo python3 -m pip install --upgrade internetarchive

Mac OS X
~~~~~~~~

While newer versions Mac OS X ship with Python 3 installed, it is recommended to install an updated version of Python 3.
You can do so with `Homebrew <https://brew.sh/#install>`_::

    $ brew install python3

Installing Pip
~~~~~~~~~~~~~~

If you are running Python 3.4+, you should already have ``pip`` installed.
If it is not already installed, it can be `installed with the get-pip.py script <https://pip.pypa.io/en/stable/installing/>`_::

    $ curl -LOs https://bootstrap.pypa.io/get-pip.py
    $ python3 get-pip.py


virtualenv
----------

If you don't want to, or can't, install the package system-wide you can use ``virtualenv`` to create an isolated Python environment.

First, make sure ``virtualenv`` is installed on your system. If it's not, you can do so with pip::

    $ sudo python3 -m pip install virtualenv

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


Binaries
--------

Binaries are also available for the ``ia`` command-line tool::

    $ curl -LOs https://archive.org/download/ia-pex/ia
    $ chmod +x ia

Binaries are generated with `PEX <https://github.com/pantsbuild/pex>`_. The only requirement for using the binaries is that you have Python 3 installed on a Unix-like operating system.

For more details on the command-line interface please refer to the `README <https://github.com/jjjake/internetarchive/blob/master/README.rst>`_, or ``ia help``.


Python 2
--------

If you are on an older operating system that only has Python 2 installed, it's highly suggested that you upgrade to Python 3. If for any reason you are not able to, the latest version of ``ia`` that supports Python 2 is 2.3.0.

You can install and use version v2.3.0 with pip::

    $ sudo python2 -m pip install internetarchive==2.3.0

You can also download a binary of v2.3.0::

    $ curl -LOs https://archive.org/download/ia-pex/ia-py2
    $ chmod +x ia-py2


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
