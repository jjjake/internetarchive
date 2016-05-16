.. :changelog:

Release History
---------------

1.0.3 (2016-05-16)
++++++++++++++++++

**Features and Improvements**

- Use scrape API for getting total number of results rather than the advanced search API.
- Improved error messages for IA-S3 (upload) related errors.
- Added retry suport to delete.
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

- Fixed memory leak in `ia upload --spreadsheet=metadata.csv`.
- Fixed arg parsing bug in `ia` CLI.

1.0.0 (2016-03-01)
++++++++++++++++++

**Features and Improvements**

- Renamed ``internetarchive.iacli`` to ``internetarchive.cli``.
- Moved ``File`` object to ``internetarchive.files``.
- Converted config fromat from YAML to INI to avoid PyYAML requirement.
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

- Fixed `ia help` bug.
- Fixed bug in `File.download()` where connection errors weren't being caught/retried correctly.

0.9.7 (2015-11-05)
++++++++++++++++++

**Bugfixes**

- Cleanup partially downloaded files when `download()` fails.

**Features and Improvements**

- Added `--format` option to `ia delete`.
- Refactored `download()` and `ia download` to behave more like rsync. Files are now clobbered by default,
  `ignore_existing` and `--ignore-existing` now skip over files already downloaded without making a request.
- Added retry support to `download()` and `ia download`.
- Added `files` kwarg to `Item.download()` for downloading specific files.
- Added `ignore_errors` option to `File.download()` for ignoring (but logging) exceptions.
- Added default timeouts to metadata and download requests.
- Less verbose output in `ia download` by default, use `ia download --verbose` for old style output.

0.9.6 (2015-10-12)
++++++++++++++++++

**Bugfixes**

- Removed sync-db features for now, as lazytaable is not playing nicely with setup.py right now.

0.9.5 (2015-10-12)
++++++++++++++++++

**Features and Improvements**

- Added skip based on mtime and length if no other clobber/skip options specified in `download()` and `ia download`.

0.9.4 (2015-10-01)
++++++++++++++++++

**Features and Improvements**

- Added `internetarchive.api.get_username()` for retrieving a username with an S3 key-pair.
- Added ability to sync downloads via an sqlite database.

0.9.3 (2015-09-28)
++++++++++++++++++

**Features and Improvements**

- Added ability to download items from an itemlist or search query in `ia download`.
- Made `ia configure` Python 3 compatabile.

**Bugfixes**

- Fixed bug in `ia upload` where uploading an item with more than one collection specified caused the collection check to fail.


0.9.2 (2015-08-17)
++++++++++++++++++

**Bugfixes**

- Added error message for failed `ia configure` calls due to invalid creds. 


0.9.1 (2015-08-13)
++++++++++++++++++

**Bugfixes**

- Updated docopt to v0.6.2 and PyYAML to v3.11.
- Updated setup.py to automatically pull version from `__init__`.


0.8.5 (2015-07-13)
++++++++++++++++++

**Bugfixes**

- Fixed UnicodeEncodeError in `ia metadata --append`.

**Features and Improvements**

- Added configuration documentation to readme.
- Updated requests to v2.7.0

0.8.4 (2015-06-18)
++++++++++++++++++

**Features and Improvements**

- Added check to `ia upload` to see if the collection being uploaded to exists.
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

- Fixed bug in `internetarchive.config.get_auth_config` (i.e. `ia configure`)
  where logged-in cookies returned expired within hours. Cookies should now be
  valid for about one year.

0.7.8 (2014-12-23)
++++++++++++++++++

- Output error message when downloading non-existing files in `ia download` rather
  than raising Python exception.
- Fixed IOError in `ia search` when using `head`, `tail`, etc..
- Simplified `ia search` to output only JSON, rather than doing any special
  formatting.
- Added experimental support for creating pex binaries of ia in `Makefile`. 

0.7.7 (2014-12-17)
++++++++++++++++++

- Simplified `ia configure`. It now only asks for Archive.org email/password and
  automatically adds S3 keys and Archive.org cookies to config.
  See `internetarchive.config.get_auth_config()`.

0.7.6 (2014-12-17)
++++++++++++++++++

- Write metadata to stdout rather than stderr in `ia mine`.
- Added options to search archive.org/v2.
- Added destdir option to download files/itemdirs to a given destination dir.

0.7.5 (2014-10-08)
++++++++++++++++++

- Fixed typo.

0.7.4 (2014-10-08)
++++++++++++++++++

- Fixed missing "import" typo in `internetarchive.iacli.ia_upload`.

0.7.3 (2014-10-08)
++++++++++++++++++

- Added progress bar to `ia mine`.
- Fixed unicode metadata support for `upload()`.

0.7.2 (2014-09-16)
++++++++++++++++++

- Suppress `KeyboardInterrupt` exceptions and exit with status code 130.
- Added ability to skip downloading files based on checksum in `ia download`,
  `Item.download()`, and `File.download()`.
- `ia download` is now verbose by default. Output can be suppressed with the `--quiet`
  flag.
- Added an option to not download into item directories, but rather the current working
  directory (i.e. `ia download --no-directories <id>`).
- Added/fixed support for modifying different metadata targets (i.e. files/logo.jpg).

0.7.1 (2014-08-25)
++++++++++++++++++

- Added `Item.s3_is_overloaded()` method for S3 status check. This method is now used on
  retries in the upload method now as well. This will avoid uploading any data if a 503
  is expected. If a 503 is still returned, retries are attempted.
- Added `--status-check` option to `ia upload` for S3 status check.
- Added `--source` parameter to `ia list` for returning files matching IA source (i.e. 
  original, derivative, metadata, etc.).
- Added support to `ia upload` for setting remote-name if only a single file is being
  uploaded.
- Derive tasks are now only queued after the last file has been uploaded.
- File URLs are now quoted in `File` objects, for downloading files with specail
  characters in their filenames

0.7.0 (2014-07-23)
++++++++++++++++++

- Added support for retry on S3 503 SlowDown errors.

0.6.9 (2014-07-15)
++++++++++++++++++

- Added support for \n and \r characters in upload headers.
- Added support for reading filenames from stdin when using the `ia delete` command.

0.6.8 (2014-07-11)
++++++++++++++++++

- The delete `ia` subcommand is now verbose by default.
- Added glob support to the delete `ia` subcommand (i.e. `ia delete --glob='*jpg'`).
- Changed indexed metadata elements to clobber values instead of insert.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are now deprecated.
  IAS3_ACCESS_KEY and IAS3_SECRET_KEY must be used if setting IAS3
  keys via environment variables.
