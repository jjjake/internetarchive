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
- Code style and formatting are enforced by `ruff <https://docs.astral.sh/ruff/>`_ (configured in `pyproject.toml <https://github.com/jjjake/internetarchive/blob/master/pyproject.toml>`_). Run ``ruff check`` and ``ruff format --check`` before submitting; CI will fail if your patch is not clean.
- Add yourself to AUTHORS.rst.
- Avoid introducing new dependencies.
- Open an issue if a relevant one is not already open, so others have visibility into what you're working on and efforts aren't duplicated.
- Clarity is preferred over brevity.

Running Tests
-------------

Clone the `internetarchive lib <https://github.com/jjjake/internetarchive>`_:

.. code:: bash

    $ git clone https://github.com/jjjake/internetarchive

Install it as an editable package with its test dependencies:

.. code:: bash

    $ cd internetarchive
    $ pip install -e '.[test]'

Run the linter, the format check, and the tests:

.. code:: bash

    $ ruff check && ruff format --check && pytest

Note that this will only test against the Python version you are currently using, however ``internetarchive`` tests against multiple Python versions defined in `tox.ini <https://github.com/jjjake/internetarchive/blob/master/tox.ini>`_. Tests must pass on all versions defined in ``tox.ini`` for all pull requests.

To test against all supported Python versions, first make sure you have all of the required versions of Python installed. Then install and execute tox from the root directory of the repo:

.. code:: bash

    $ pip install tox
    $ tox

Even easier is simply creating a pull request. `GitHub Actions <https://docs.github.com/en/actions>`_ are used for continuous integration, and are set up to run the full testsuite whenever a pull request is submitted or updated.

Releasing
---------

``master`` is branch-protected (pull requests and required status checks; no direct pushes), so a release is three steps: land the version bump through a pull request, push the release tag, and upload the ``pex`` binary to archive.org.

#. **Bump the version (via a PR).** On a branch, run ``make prepare-release RELEASE=X.Y.Z`` -- this sets ``internetarchive/__version__.py`` (and the ``HISTORY.rst`` date when the heading is ``X.Y.Z (?)``). Open a pull request with those changes and merge it once CI passes.

#. **Tag.** Update your local ``master`` and push the release tag:

   .. code:: bash

       $ git checkout master && git pull
       $ make check-version check-release tag push-tag

   Pushing the ``vX.Y.Z`` tag triggers the ``release`` GitHub Actions workflow, which runs the tests, builds and validates the sdist/wheel and ``pex`` binary, publishes to PyPI via `Trusted Publishing <https://docs.pypi.org/trusted-publishers/>`_ (OIDC -- no PyPI token involved), and creates the GitHub release with the curated ``HISTORY.rst`` notes and the ``pex`` (plus its sha256) attached.

#. **Upload the binary to archive.org.** CI has no archive.org credentials, so upload the ``pex`` to the `ia-pex item <https://archive.org/details/ia-pex>`_ from your machine:

   .. code:: bash

       $ make publish-binary

**Fallback:** if the release workflow is unavailable, ``make publish`` still performs the entire release from your machine -- tests, builds, tag push, PyPI upload (requires a PyPI API token), archive.org upload, and the GitHub release. Don't run it after CI has already published; the PyPI upload and GitHub release steps will fail as duplicates.
