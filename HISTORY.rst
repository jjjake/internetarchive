.. :changelog:

Release History
---------------

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
