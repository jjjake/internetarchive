.. :changelog:

Release History
---------------

0.7.0 (?)
+++++++++
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
