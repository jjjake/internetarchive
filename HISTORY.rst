.. :changelog:

Release History
---------------

3.0.1 (2022-06-02)
++++++++++++++++++

**Features and Improvements**

- Cut down on the number of HTTP requests made by search.
- Added Python type hints, and other Python 3 improvements.

3.0.0 (2022-03-17)
++++++++++++++++++

**Breaking changes**

- Removed Python 2.7, 3.5, and 3.6 support
- ``ia download`` no longer has a ``--verbose`` option, and ``--silent`` has been renamed to ``--quiet``.
- ``internetarchive.download``, ``Item.download`` and ``File.download`` no longer have a ``silent``
  keyword argument. They are silent by default now unless ``verbose`` is set to ``True``.

**Features and Improvements**

- ``page`` parameter is no longer required if ``rows`` parameter is specified in search requests.
- advancedsearch.php endpoint now supports IAS3 authorization.
- ``ia upload`` now has a ``--keep-directories`` option to use the full local file paths as the
  remote name.
- Added progress bars to ``ia download``

**Bugfixes**

- Fixed treatment of list-like file metadata in ``ia list`` under Python 3
- Fixed ``ia upload --debug`` only displaying the first request.
- Fixed uploading from stdin crashing with UnicodeDecodeError or TypeError exception.
- Fixed ``ia upload`` silently ignoring exceptions.
- Fixed uploading from a spreadsheet with a BOM (UTF-8 byte-order mark) raising a KeyError.
- Fixed uploading from a spreadsheet not reusing the ``identifier`` column.
- Fixed uploading from a spreadsheet not correctly dropping the ``item`` column from metadata.
- Fixed uploading from a spreadsheet with ``--checksum`` crashing on skipped files.
- Fixed minor bug in S3 overload check on upload error retries.
- Fixed various messages being printed to stdout instead of stderr.
- Fixed format selection for on-the-fly files.

2.3.0 (2022-01-20)
++++++++++++++++++

**Features and Improvements**

- Added support for ``IA_CONFIG_FILE`` environment variable to specify the configuration file path.
- Added ``--no-derive`` option to ``ia copy`` and ``ia move``.
- Added ``--no-backup`` option to ``ia copy``, ``ia move``, ``ia upload``, and ``ia delete``.

**Bugfixes**

- Fixed bug where queries to the Scrape API (e.g. most search requests made by ``internetarchive``)
  would fail to return all docs without any error reporting, if the Scrape API times out.
  All queries to the Scrape API are now tested to assert the number of docs returned matches the
  hit count returned by the Scrape API.
  If these numbers don't match, an exception is thrown in the Python API and the CLI exits with
  a non-zero exit code and error message.
- Use .archive.org as the default cookie domain. This fixes a bug where an AttributeError exception
  would be raised if a cookie wasn't set in a config file.

2.2.0 (2021-11-23)
++++++++++++++++++

**Features and Improvements**

- Added ``ia reviews <id> --delete``.
- Added ability to fetch a users reviews from an item via ``ia reviews <id>``.

**Bugfixes**

- Fixed bug in ``ArchiveSession`` object where domains weren't getting set properly for cookies.
  This caused archive.org cookies to be sent to other domains.
- Fixed bug in URL param parser for CLI.
- Fixed Python 2 bug in ``ia upload --spreadsheet``.

2.1.0 (2021-08-25)
++++++++++++++++++

**Features and Improvements**

- Better error messages in ``ia upload --spreadsheet``.
- Added support for REMOTE_NAME in ``ia upload --spreadsheet`` via a ``REMOTE_NAME`` column.
- Implemented XDG Base Directory specification.

**Bugfixes**

- Fixed bug in FTS where searches would crash with a TypeError exception.
- Improved Python 2 compatibility.

2.0.3 (2021-05-03)
++++++++++++++++++

**Bugfixes**

- Fixed bug where some "falsey"/empty values were being dropped when modifying metadata.

2.0.2 (2021-04-06)
++++++++++++++++++

- Fixing pypi issues...

2.0.1 (2021-04-06)
++++++++++++++++++

**Bugfixes**

- Exit with 0 in ``ia tasks --cmd ...`` if a task is already queued or running.

2.0.0 (2021-04-05)
++++++++++++++++++

**Features and Improvements**

- Automatic paging scrolling added to ``ia search --fts``.
- Default support for lucene queries in ``ia search --fts``.
- Added support for getting rate-limit information from the Tasks API (i.e. ``ia tasks --get-rate-limit --cmd derive.php``).
- Added ability to set a remote-filename in a spreadsheet when uploading via ``ia upload --spreadsheet ...``.

**Bugfixes**

- Fixed bug in ``ia metadata --remove ...`` where multiple collections would be removed
  if the specified collection was a substring of any of the existing collections.
- Fixed bug in ``ia metadata --remove ...`` where removing multiple collections was sometimes
  not supported.

1.9.9 (2021-01-27)
++++++++++++++++++

**Features and Improvements**

- Added support for FTS API.
- Validate identifiers in spreadsheet before uploading file with ``ia upload --spreadsheet``.
- Added ``ia configure --print-cookies``.
  This is helpful for using your archive.org cookies in other programs like ``curl``.
  e.g. ``curl -b $(ia configure --print-cookies) <url> ...``

1.9.6 (2020-11-10)
++++++++++++++++++

**Features and Improvements**

- Added ability to submit tasks with a reduced priority.
- Added ability to add headers to modify_metadata requests.

**Bugfixes**

- Bumped version requirements for ``six``.
  This addresses the "No module named collections_abc" error.

1.9.5 (2020-09-18)
++++++++++++++++++

**Features and Improvements**

- Increased chunk size in download and added other download optimizations.
- Added support for submitting reviews via ``Item.review()`` and ``ia review``.
- Improved exception/error messages in cases where s3.us.archive.org returns invalid XML during uploads.
- Minor updates and improvements to continuous integration.

1.9.4 (2020-06-24)
++++++++++++++++++

**Features and Improvements**

- Added support for adding file-level metadata at time of upload.
- Added ``--no-backup`` to ``ia upload`` to turn off backups.

**Bugfixes**

- Fixed bug in ``internetarchive.get_tasks`` where no tasks were returned unless ``catalog`` or ``history`` params were provided.
- Fixed bug in upload where headers were being reused in certain cases.
  This lead to issues such as queue-derive being turned off in some cases.
- Fix crash in ``ia tasks`` when a task log contains invalid UTF-8 character.
- Fixed bug in upload where requests were not being closed.

1.9.3 (2020-04-07)
++++++++++++++++++

**Features and Improvements**

- Added support for remvoing items from simplelists as if they were collections.
- Added ``Item.derive()`` method for deriving items.
- Added ``Item.fixer()`` method for submitting fixer tasks.
- Added ``--task-args`` to ``ia tasks`` for submitting task args to the Tasks API.

**Bugfixes**

- Minor bug fix in ``ia tasks`` to fix support for tasks that do not require a ``--comment`` option.

1.9.2 (2020-03-15)
++++++++++++++++++

**Features and Improvements**

- Switched to ``tqdm`` for progress bar (``clint`` is no longer maintained).
- Added ``Item.identifier_available()`` method for calling check_identifier.php.
- Added support for opening details page in default browser after upload.
- Added support for using ``item`` or ``identifier`` as column header in spreadsheet mode.
- Added ``ArchiveSession.get_my_catalog()`` method for retrieving running/queued tasks.
- Removed backports.csv requirement for newer Python releases.
- Authorization header is now used for metadata reads, to support privileged access to /metadata.
- ``ia download`` no longer downloads history dir by default.
- Added ``ignore_history_dir`` to ``Item.download()``. The default is False.

**Bugfixes**

- Fixed bug in ``ia copy`` and ``ia move`` where filenames weren't being encoded/quoted correctly.
- Fixed bug in ``Item.get_all_item_tasks()`` where all calls would fail unless a dict was provided to ``params``.
- Read from ~/.config/ia.ini with fallback to ~/.ia regardless of the existence of ~/.config
- Fixed S3 overload message always mentioning the total maximum number of retries, not the remaining ones.
- Fixed bug where a KeyError exception would be raised on most calls to dark items.
- Fixed bug where md5 was being calculated for every upload.

1.9.0 (2019-12-05)
++++++++++++++++++

**Features and Improvements**

- Implemented new archive.org `Tasks API <https://archive.org/services/docs/api/tasks.html>`_.
- Added support for darking and undarking items via the Tasks API.
- Added support for submitting arbitrary tasks
  (only darking/undarking currently supported, see Tasks API documentation).

**Bugfixes**

- ``ia download`` now displays ``download failed`` instead of ``success`` when download fails.
- Fixed bug where ``Item.get_file`` would not work on unicode names in Python 2.

1.8.5 (2019-06-07)
++++++++++++++++++

**Features and Improvements**

- Improved timeout logging and exceptions.
- Added support for arbitrary targets to metadata write.
- IA-S3 keys now supported for auth in download.
- Authoraization (i.e. ``ia configure``) now uses the archive.org xauthn endpoint.

**Bugfixes**

- Fixed encoding error in --get-task-log
- Fixed bug in upload where connections were not being closed in upload.

1.8.4 (2019-04-11)
++++++++++++++++++

**Features and Improvements**

- It's now possible to retrieve task logs, given a task id, without first retrieving the items task history.
- Added examples to ``ia tasks`` help.

1.8.3 (2019-03-29)
++++++++++++++++++

**Features and Improvements**

- Increased search timeout from 24 to 300 seconds.

**Bugfixes**

- Fixed bug in setup.py where backports.csv wasn't being installed when installing from pypi.

1.8.2 (2019-03-21)
++++++++++++++++++

**Features and Improvements**

- Documnetation updates.
- Added support for write-many to modify_metadata.

**Bugfixes**

- Fixed bug in ``ia tasks --task-id`` where no task was being returned.
- Fixed bug in ``internetarchive.get_tasks()`` where it was not possible to query by ``task_id``.
- Fixed TypeError bug in upload when uploading with checksum=True.

1.8.1 (2018-06-28)
++++++++++++++++++

**Bugfixes**

- Fixed bug in ``ia tasks --get-task-log`` that was returning an unable to parse JSON error.

1.8.0 (2018-06-28)
++++++++++++++++++

**Features and Improvements**

- Only use backports.csv for python2 in support of FreeBDS port.
- Added a nicer error message to ``ia search`` for authentication errors.
- Added support for using netrc files in ``ia configure``.
- Added ``--remove`` option to ``ia metadata`` for removing values from single or mutli-field metadata elements.
- Added support for appending a metadata value to an existing metadata element (as a new entry, not simply appending to a string).
- Added ``--no-change-timestamp`` flag to ``ia download``.
  Download files retain the timestamp of "now", not of the source material when this option is used.

**Bugfixes**

- Fixed bug in upload where StringIO objects were not uploadable.
- Fixed encoding issues that were causing some ``ia tasks`` commands to fail.
- Fixed bug where keep-old-version wasn't working in ``ia move``.
- Fixed bug in ``internetarchive.api.modify_metadata`` where debug and other args were not honoured.

1.7.7 (2018-03-05)
++++++++++++++++++

**Features and Improvements**

- Added support for downloading on-the-fly archive_marc.xml files.

**Bugfixes**

- Improved syntax checking in ``ia move`` and ``ia copy``.
- Added ``Connection:close`` header to all requests to force close connections after each request.
  This is a workaround for dealing with a bug on archive.org servers where the server hangs up before sending the complete response.

1.7.6 (2018-01-05)
++++++++++++++++++

**Features and Improvements**

- Added ability to set the remote-name for a directory in ``ia upload`` (previously you could only do this for single files).

**Bugfixes**

- Fixed bug in ``ia delete`` where all requests were failing due to a typo in a function arg.

1.7.5 (2017-12-07)
++++++++++++++++++

**Features and Improvements**

- Turned on ``x-archive-keep-old-version`` S3 header by default for all ``ia upload``, ``ia delete``, ``ia copy``, and ``ia move`` commands.
  This means that any ``ia`` command that clobbers or deletes a command, will save a version of the file in ``<identifier>/history/files/$key.~N~``.
  This is only on by default in the CLI, and not in the Python lib.
  It can be turne off by adding ``-H x-archive-keep-old-version:0`` to any ``ia upload``, ``ia delete``, ``ia copy``, or ``ia move`` command.

1.7.4 (2017-11-06)
++++++++++++++++++

**Features and Improvements**

- Increased timeout in search from 12 seconds to 24.
- Added ability to set the ``max_retries`` in :func:`internetarchive.search_items`.
- Made :meth:`internetarchive.ArchiveSession.mount_http_adapter` a public method for supporting complex custom retry logic.
- Added ``--timeout`` option to ``ia search`` for setting a custom timeout.
- Loosened requirements for schema library to ``schema>=0.4.0``.

**Bugfixes**

- The scraping API has reverted to using ``items`` key rather than ``docs`` key.
  v1.7.3 will still work, but this change keeps ia consistent with the API.

1.7.3 (2017-09-20)
++++++++++++++++++

**Bugfixes**

- Fixed bug in search where search requests were failing with ``KeyError: 'items'``.

1.7.2 (2017-09-11)
++++++++++++++++++

**Features and Improvements**

- Added support for adding custom headers to ``ia search``.

**Bugfixes**

- ``internetarchive.utils.get_s3_xml_text()`` is used to parse errors returned by S3 in XML.
  Sometimes there is no XML in the response.
  Most of the time this is due to 5xx errors.
  Either way, we want to always return the HTTPError, even if the XML parsing fails.
- Fixed a regression where ``:`` was being stripped from filenames in upload.
- Do not create a directory in ``download()`` when ``return_responses`` is ``True``.
- Fixed bug in upload where file-like objects were failing with a TypeError exception.

1.7.1 (2017-07-25)
++++++++++++++++++

**Bugfixes**

- Fixed bug in ``Item.upload_file()`` where ``checksum`` was being set to ``True`` if it was set to ``None``.

1.7.1 (2017-07-25)
++++++++++++++++++

**Bugfixes**

- Fixed bug in ``ia upload`` where all commands would fail if multiple collections were specified (e.g. -m collection:foo -m collection:bar).

1.7.0 (2017-07-25)
++++++++++++++++++

**Features and Improvements**

- Loosened up ``jsonpatch`` requirements, as the metadata API now supports more recent versions of the JSON Patch standard.
- Added support for building "snap" packages (https://snapcraft.io/).

**Bugfixes**

- Fixed bug in upload where users were unable to add their own timeout via ``request_kwargs``.
- Fixed bug where files with non-ascii filenames failed to upload on some platforms.
- Fixed bug in upload where metadata keys with an index (e.g. ``subject[0]``) would make the request fail if the key was the only indexed key provided.
- Added a default timeout to ``ArchiveSession.s3_is_overloaded()``.
  If it times out now, it returns ``True`` (as in, yes, S3 is overloaded).

1.6.0 (2017-06-27)
++++++++++++++++++

**Features and Improvements**

- Added 60 second timeout to all upload requests.
- Added support for uploading empty files.
- Refactored ``Item.get_files()`` to be faster, especially for items with many files.
- Updated search to use IA-S3 keys for auth instead of cookies.

**Bugfixes**

- Fixed bug in upload where derives weren't being queued in some cases where checksum=True was set.
- Fixed bug where ``ia tasks`` and other ``Catalog`` functions were always using HTTP even when it should have been HTTPS.
- ``ia metadata`` was exiting with a non-zero status for "no changes to xml" errors.
  This now exits with 0, as nearly every time this happens it should not be considered an "error".
- Added unicode support to ``ia upload --spreadsheet`` and ``ia metadata --spreadsheet`` using the ``backports.csv`` module.
- Fixed bug in ``ia upload --spreadsheet`` where some metadata was accidentally being copied from previous rows
  (e.g. when multiple subjects were used).
- Submitter wasn't being added to ``ia tasks --json`` output, it now is.
- ``row_type`` in ``ia tasks --json`` was returning integer for row-type rather than name (e.g. 'red').

1.5.0 (2017-02-17)
++++++++++++++++++

**Features and Improvements**

- Added option to download() for returning a list of response objects
  rather than writing files to disk.

1.4.0 (2017-01-26)
++++++++++++++++++

**Bugfixes**

- Another bugfix for setting mtime correctly after ``fileobj`` functionality was added to ``ia download``.

1.3.0 (2017-01-26)
++++++++++++++++++

**Bugfixes**

- Fixed bug where download was trying to set mtime, even when ``fileobj`` was set to ``True``
  (e.g. ``ia download <id> <file> --stdout``).

1.2.0 (2017-01-26)
++++++++++++++++++

**Features and Improvements**

- Added ``ia copy`` and ``ia move`` for copying and moving files in archive.org items.
- Added support for outputting JSON in ``ia tasks``.
- Added support to ``ia download`` to write to stdout instead of file.

**Bugfixes**

- Fixed bug in upload where AttributeError was raised when trying to upload file-like objects without a name attribute.
- Removed identifier validation from ``ia delete``.
  If an identifier already exists, we don't need to validate it.
  This only makes things annoying if an identifier exists but fails ``internetarchive`` id validation.
- Fixed bug where error message isn't returned in ``ia upload`` if the response body is not XML.
  Ideally IA-S3 would always return XML, but that's not the case as of now.
  Try to dump the HTML in the S3 response if unable to parse XML.
- Fixed bug where ArchiveSession headers weren't being sent in prepared requests.
- Fixed bug in ``ia upload --size-hint`` where value was an integer, but requests requires it to be a string.
- Added support for downloading files to stdout in ``ia download`` and ``File.download``.

1.1.0 (2016-11-18)
++++++++++++++++++

**Features and Improvements**

- Make sure collection exists when creating new item via ``ia upload``. If it doesn't, upload will fail.
- Refactored tests.

**Bugfixes**

- Fixed bug where the full filepath was being set as the remote filename in Windows.
- Convert all metadata header values to strings for compatibility with ``requests>=2.11.0``.

1.0.10 (2016-09-20)
+++++++++++++++++++

**Bugfixes**

- Convert x-archive-cascade-delete headers to strings for compatibility with ``requests>=2.11.0``.

1.0.9 (2016-08-16)
++++++++++++++++++

**Features and Improvements**

- Added support to the CLI for providing username and password as options on the command-line.

1.0.8 (2016-08-10)
++++++++++++++++++

**Features and Improvements**

- Increased maximum identifier length from 80 to 100 characters in ``ia upload``.

**Bugfixes**

- As of version 2.11.0 of the requests library, all header values must be strings (i.e. not integers).
  ``internetarchive`` now converts all header values to strings.

1.0.7 (2016-08-02)
++++++++++++++++++

**Features and Improvements**

- Added ``internetarchive.api.get_user_info()``.

1.0.6 (2016-07-14)
++++++++++++++++++

**Bugfixes**

- Fixed bug where upload was failing on file-like objects (e.g. StringIO objects).

1.0.5 (2016-07-07)
++++++++++++++++++

**Features and Improvements**

- All metadata writes are now submitted at -5 priority by default.
  This is friendlier to the archive.org catalog, and should only be changed for one-off metadata writes.
- Expanded scope of valid identifiers in ``utils.validate_ia_identifier`` (i.e. ``ia upload``).
  Periods are now allowed.
  Periods, underscores, and dashes are not allowed as the first character.

1.0.4 (2016-06-28)
++++++++++++++++++

**Features and Improvements**

- Search now uses the v1 scraping API endpoint.
- Moved ``internetarchive.item.Item.upload.iter_directory()`` to ``internetarchive.utils``.
- Added support for downloading "on-the-fly" files (e.g. EPUB, MOBI, and DAISY) via ``ia download <id> --on-the-fly`` or ``item.download(on_the_fly=True)``.

**Bugfixes**

- ``s3_is_overloaded()`` now returns ``True`` if the call is unsuccessful.
- Fixed bug in upload where a derive task wasn't being queued when a directory is uploaded.

1.0.3 (2016-05-16)
++++++++++++++++++

**Features and Improvements**

- Use scrape API for getting total number of results rather than the advanced search API.
- Improved error messages for IA-S3 (upload) related errors.
- Added retry support to delete.
- ``ia delete`` no longer exits if a single request fails when deleting multiple files, but continues onto the next file.
  If any file fails, the command will exit with a non-zero status code.
- All search requests now require authentication via IA-S3 keys.
  You can run ``ia configure`` to generate a config file that will be used to authenticate all search requests automatically.
  For more details refer to the following links:

  http://internetarchive.readthedocs.io/en/latest/quickstart.html?highlight=configure#configuring

  http://internetarchive.readthedocs.io/en/latest/api.html#configuration

- Added ability to specify your own filepath in ``ia configure`` and ``internetarchive.configure()``.

**Bugfixes**

- Updated ``requests`` lib version requirements.
  This resolves issues with sending binary strings as bodies in Python 3.
- Improved support for Windows, see `https://github.com/jjjake/internetarchive/issues/126 <https://github.com/jjjake/internetarchive/issues/126>`_ for more details.
- Previously all requests were made in HTTP for Python versions < 2.7.9 due to the issues described at `https://urllib3.readthedocs.org/en/latest/security.html <https://urllib3.readthedocs.org/en/latest/security.html>`_.
  In favor of security over convenience, all requests are now made via HTTPS regardless of Python version.
  Refer to `http://internetarchive.readthedocs.org/en/latest/troubleshooting.html#https-issues <http://internetarchive.readthedocs.org/en/latest/troubleshooting.html#https-issues>`_ if you are experiencing issues.
- Fixed bug in ``ia`` CLI where ``--insecure`` was still making HTTPS requests when it should have been making HTTP requests.
- Fixed bug in ``ia delete`` where ``--all`` option wasn't working because it was using ``item.iter_files`` instead of ``item.get_files``.
- Fixed bug in ``ia upload`` where uploading files with unicode file names were failing.
- Fixed bug in upload where filenames with ``;`` characters were being truncated.
- Fixed bug in ``internetarchive.catalog`` where TypeError was being raised in Python 3 due to mixing bytes with strings.

1.0.2 (2016-03-07)
++++++++++++++++++

**Bugfixes**

- Fixed OverflowError bug in uploads on 32-bit systems when uploading files larger than ~2GB.
- Fixed unicode bug in upload where ``urllib.parse.quote`` is unable to parse non-encoded strings.

**Features and Improvements**

- Only generate MD5s in upload if they are used (i.e. verify, delete, or checksum is True).
- verify is off by default in ``ia upload``, it can be turned on with ``ia upload --verify``.

1.0.1 (2016-03-04)
++++++++++++++++++

**Bugfixes**

- Fixed memory leak in ``ia upload --spreadsheet=metadata.csv``.
- Fixed arg parsing bug in ``ia`` CLI.

1.0.0 (2016-03-01)
++++++++++++++++++

**Features and Improvements**

- Renamed ``internetarchive.iacli`` to ``internetarchive.cli``.
- Moved ``File`` object to ``internetarchive.files``.
- Converted config format from YAML to INI to avoid PyYAML requirement.
- Use HTTPS by default for Python versions > 2.7.9.
- Added ``get_username`` function to API.
- Improved Python 3 support. ``internetarchive`` is now being tested against Python versions 2.6, 2.7, 3.4, and 3.5.
- Improved plugin support.
- Added retry support to download and metadata retrieval.
- Added ``Collection`` object.
- Made ``Item`` objects hashable and orderable.

**Bugfixes**

- IA's Advanced Search API no longer supports deep-paging of large result sets.
  All search functions have been refactored to use the new Scrape API (http://archive.org/help/aboutsearch.htm).
  Search functions in previous versions are effictively broken, upgrade to >=1.0.0.

0.9.8 (2015-11-09)
++++++++++++++++++

**Bugfixes**

- Fixed ``ia help`` bug.
- Fixed bug in ``File.download()`` where connection errors weren't being caught/retried correctly.

0.9.7 (2015-11-05)
++++++++++++++++++

**Bugfixes**

- Cleanup partially downloaded files when ``download()`` fails.

**Features and Improvements**

- Added ``--format`` option to ``ia delete``.
- Refactored ``download()`` and ``ia download`` to behave more like rsync. Files are now clobbered by default,
  ``ignore_existing`` and ``--ignore-existing`` now skip over files already downloaded without making a request.
- Added retry support to ``download()`` and ``ia download``.
- Added ``files`` kwarg to ``Item.download()`` for downloading specific files.
- Added ``ignore_errors`` option to ``File.download()`` for ignoring (but logging) exceptions.
- Added default timeouts to metadata and download requests.
- Less verbose output in ``ia download`` by default, use ``ia download --verbose`` for old style output.

0.9.6 (2015-10-12)
++++++++++++++++++

**Bugfixes**

- Removed sync-db features for now, as lazytaable is not playing nicely with setup.py right now.

0.9.5 (2015-10-12)
++++++++++++++++++

**Features and Improvements**

- Added skip based on mtime and length if no other clobber/skip options specified in ``download()`` and ``ia download``.

0.9.4 (2015-10-01)
++++++++++++++++++

**Features and Improvements**

- Added ``internetarchive.api.get_username()`` for retrieving a username with an S3 key-pair.
- Added ability to sync downloads via an sqlite database.

0.9.3 (2015-09-28)
++++++++++++++++++

**Features and Improvements**

- Added ability to download items from an itemlist or search query in ``ia download``.
- Made ``ia configure`` Python 3 compatible.

**Bugfixes**

- Fixed bug in ``ia upload`` where uploading an item with more than one collection specified caused the collection check to fail.


0.9.2 (2015-08-17)
++++++++++++++++++

**Bugfixes**

- Added error message for failed ``ia configure`` calls due to invalid creds.


0.9.1 (2015-08-13)
++++++++++++++++++

**Bugfixes**

- Updated docopt to v0.6.2 and PyYAML to v3.11.
- Updated setup.py to automatically pull version from ``__init__``.


0.8.5 (2015-07-13)
++++++++++++++++++

**Bugfixes**

- Fixed UnicodeEncodeError in ``ia metadata --append``.

**Features and Improvements**

- Added configuration documentation to readme.
- Updated requests to v2.7.0

0.8.4 (2015-06-18)
++++++++++++++++++

**Features and Improvements**

- Added check to ``ia upload`` to see if the collection being uploaded to exists.
  Also added an option to override this check.

0.8.3 (2015-05-18)
++++++++++++++++++

**Features and Improvements**

- Fixed append to work like a standard metadata update if the metadata field
  does not yet exist for the given item.

0.8.0 2015-03-09
++++++++++++++++

**Bugfixes**

- Encode filenames in upload URLs.

0.7.9 (2015-01-26)
++++++++++++++++++

**Bugfixes**

- Fixed bug in ``internetarchive.config.get_auth_config`` (i.e. ``ia configure``)
  where logged-in cookies returned expired within hours. Cookies should now be
  valid for about one year.

0.7.8 (2014-12-23)
++++++++++++++++++

- Output error message when downloading non-existing files in ``ia download`` rather
  than raising Python exception.
- Fixed IOError in ``ia search`` when using ``head``, ``tail``, etc..
- Simplified ``ia search`` to output only JSON, rather than doing any special
  formatting.
- Added experimental support for creating pex binaries of ia in ``Makefile``.

0.7.7 (2014-12-17)
++++++++++++++++++

- Simplified ``ia configure``. It now only asks for Archive.org email/password and
  automatically adds S3 keys and Archive.org cookies to config.
  See ``internetarchive.config.get_auth_config()``.

0.7.6 (2014-12-17)
++++++++++++++++++

- Write metadata to stdout rather than stderr in ``ia mine``.
- Added options to search archive.org/v2.
- Added destdir option to download files/itemdirs to a given destination dir.

0.7.5 (2014-10-08)
++++++++++++++++++

- Fixed typo.

0.7.4 (2014-10-08)
++++++++++++++++++

- Fixed missing "import" typo in ``internetarchive.iacli.ia_upload``.

0.7.3 (2014-10-08)
++++++++++++++++++

- Added progress bar to ``ia mine``.
- Fixed unicode metadata support for ``upload()``.

0.7.2 (2014-09-16)
++++++++++++++++++

- Suppress ``KeyboardInterrupt`` exceptions and exit with status code 130.
- Added ability to skip downloading files based on checksum in ``ia download``,
  ``Item.download()``, and ``File.download()``.
- ``ia download`` is now verbose by default. Output can be suppressed with the ``--quiet``
  flag.
- Added an option to not download into item directories, but rather the current working
  directory (i.e. ``ia download --no-directories <id>``).
- Added/fixed support for modifying different metadata targets (i.e. files/logo.jpg).

0.7.1 (2014-08-25)
++++++++++++++++++

- Added ``Item.s3_is_overloaded()`` method for S3 status check. This method is now used on
  retries in the upload method now as well. This will avoid uploading any data if a 503
  is expected. If a 503 is still returned, retries are attempted.
- Added ``--status-check`` option to ``ia upload`` for S3 status check.
- Added ``--source`` parameter to ``ia list`` for returning files matching IA source (i.e.
  original, derivative, metadata, etc.).
- Added support to ``ia upload`` for setting remote-name if only a single file is being
  uploaded.
- Derive tasks are now only queued after the last file has been uploaded.
- File URLs are now quoted in ``File`` objects, for downloading files with special
  characters in their filenames

0.7.0 (2014-07-23)
++++++++++++++++++

- Added support for retry on S3 503 SlowDown errors.

0.6.9 (2014-07-15)
++++++++++++++++++

- Added support for \n and \r characters in upload headers.
- Added support for reading filenames from stdin when using the ``ia delete`` command.

0.6.8 (2014-07-11)
++++++++++++++++++

- The delete ``ia`` subcommand is now verbose by default.
- Added glob support to the delete ``ia`` subcommand (i.e. ``ia delete --glob='*jpg'``).
- Changed indexed metadata elements to clobber values instead of insert.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are now deprecated.
  IAS3_ACCESS_KEY and IAS3_SECRET_KEY must be used if setting IAS3
  keys via environment variables.
