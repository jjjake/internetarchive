How to Contribute
=================

Thank you for considering contributing. All contributions are welcome and appreciated!

Support Questions
-----------------

Please don't use the Github issue tracker for asking support questions. All support questions should be emailed to `info@archive.org <mailto:info@archive.org?subject=[IA-Wrapper]>`_.

Bug Reports
-----------

`Github issues <https://github.com/jjjake/internetarchive/issues>`_ is used for tracking bugs. Please consider the following when opening an issue:

- Avoid opening duplicate issues by taking a look at the current open issues.
- Provide details on the version, operating system and Python version you are running.
- Include complete tracebacks and error messages.

Pull Requests
-------------

All pull requests and patches are welcome, but please consider the following:

- Include tests.
- Include documentation for new features.
- If your patch is supposed to fix a bug, please describe in as much detail as possible the circumstances in which the bug happens.
- Please follow `PEP8 <http://legacy.python.org/dev/peps/pep-0008/>`_, with the exception of what is ignored in `setup.cfg <https://github.com/jjjake/internetarchive/blob/master/setup.cfg>`_. PEP8 compliance is checked when tests run. Tests will fail if your patch is not PEP8 compliant.
- Add yourself to AUTHORS.rst.
- Avoid introducing new dependencies.
- Open an issue if a relevant one is not already open, so others have visibility into what you're working on and efforts aren't duplicated.
- Clarity is preferred over brevity.

Running Tests
-------------

The minimal requirements for running tests are ``pytest``, ``pytest-pep8`` and ``responses``:

.. code:: bash

    $ pip install pytest pytest-pep8 responses

Clone the `internetarchive lib <https://github.com/jjjake/internetarchive>`_:

.. code:: bash

    $ git clone https://github.com/jjjake/internetarchive

Install the `internetarchive lib <https://github.com/jjjake/internetarchive>`_ as an editable package:

.. code:: bash

    $ cd internetarchive
    $ pip install -e .

Run the tests:

.. code:: bash

    $ py.test --pep8

Note that this will only test against the Python version you are currently using, however ``internetarchive`` tests against multiple Python versions defined in `tox.ini <https://github.com/jjjake/internetarchive/blob/master/tox.ini>`_. Tests must pass on all versions defined in ``tox.ini`` for all pull requests.

To test against all supported Python versions, first make sure you have all of the required versions of Python installed. Then simply install execute tox from the root directory of the repo:

.. code:: bash

    $ pip install tox
    $ tox

Even easier is simply creating a pull request. `GitHub Actions <https://docs.github.com/en/actions>`_ are used for continuous integration, and are set up to run the full testsuite whenever a pull request is submitted or updated.

Releasing
---------

``master`` is branch-protected (pull requests and required status checks; no direct pushes), so a release is two steps: land the version bump through a pull request, then run ``make publish``.

#. **Bump the version (via a PR).** On a branch, run ``make prepare-release RELEASE=X.Y.Z`` -- this sets ``internetarchive/__version__.py`` (and the ``HISTORY.rst`` date when the heading is ``X.Y.Z (?)``). Open a pull request with those changes and merge it once CI passes.

#. **Publish.** Update your local ``master`` and run ``make publish``:

   .. code:: bash

       $ git checkout master && git pull
       $ make publish

   ``make publish`` runs the tests; builds the sdist, wheel, and ``pex`` binary; tags the release and pushes the **tag only** (never ``master``, which is protected); uploads to PyPI; uploads the ``pex`` binary to the ``ia-pex`` archive.org item; and creates the GitHub release. Use ``make publish-binary`` to re-upload just the binary if that step ever needs redoing.
