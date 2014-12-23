.. :changelog:

Release History
---------------

0.7.8 2014-12-23
++++++++++++++++
- Output error message when downloading non-existing files in `ia download` rather
  than raising Python exception.
- Fixed IOError in `ia search` when using `head`, `tail`, etc..
- Simplified `ia search` to output only JSON, rather than doing any special
  formatting.
- Added experimental support for creating pex binaries of ia in `Makefile`. 

0.7.7 2014-12-17
++++++++++++++++
- Simplified `ia configure`. It now only asks for Archive.org email/password and
  automatically adds S3 keys and Archive.org cookies to config.
  See `internetarchive.config.get_auth_config()`.

0.7.6 2014-12-17
++++++++++++++++
- Write metadata to stdout rather than stderr in `ia mine`.
- Added options to search archive.org/v2.
- Added destdir option to download files/itemdirs to a given destination dir.

0.7.5 2014-10-08
++++++++++++++++
- Fixed typo.

0.7.4 2014-10-08
++++++++++++++++
- Fixed missing "import" typo in `internetarchive.iacli.ia_upload`.

0.7.3 2014-10-08
++++++++++++++++
- Added progress bar to `ia mine`.
- Fixed unicode metadata support for `upload()`.

0.7.2 2014-09-16
++++++++++++++++
- Suppress `KeyboardInterrupt` exceptions and exit with status code 130.
- Added ability to skip downloading files based on checksum in `ia download`,
  `Item.download()`, and `File.download()`.
- `ia download` is now verbose by default. Output can be suppressed with the `--quiet`
  flag.
- Added an option to not download into item directories, but rather the current working
  directory (i.e. `ia download --no-directories <id>`).
- Added/fixed support for modifying different metadata targets (i.e. files/logo.jpg).

0.7.1 2014-08-25
++++++++++++++++
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

0.7.0 2014-07-23
++++++++++++++++
- Added support for retry on S3 503 SlowDown errors.

0.6.9 2014-07-15
++++++++++++++++
- Added support for \n and \r characters in upload headers.
- Added support for reading filenames from stdin when using the `ia delete` command.

0.6.8 2014-07-11 
++++++++++++++++

- The delete `ia` subcommand is now verbose by default.
- Added glob support to the delete `ia` subcommand (i.e. `ia delete --glob='*jpg'`).
- Changed indexed metadata elements to clobber values instead of insert.
- AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are now deprecated.
  IAS3_ACCESS_KEY and IAS3_SECRET_KEY must be used if setting IAS3
  keys via environment variables.
