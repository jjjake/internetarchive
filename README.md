## A python interface to archive.org ##

### Downloading ###

The Internet Archive stores data in [items](http://blog.archive.org/2011/03/31/how-archive-org-items-are-structured/ "How Archive.org items are structured").
You can query the archive using an item identifier:

```python
>>> import internetarchive
>>> item = internetarchive.Item('stairs')
>>> print item.metadata
```

Items contains files. You can download the entire item:

```python
>>> item.download()
```

or you can download just a particular file:

```python
>>> f = item.file('glogo.png')
>>> f.download() #writes to disk
>>> f.download('/foo/bar/some_other_name.png')
```

You can iterate over files:

```python
>>> for f in item.files():
...     print f.name, f.sha1
```

### Uploading ###

You can use the IA's S3-like interface to upload files to an item.
You need to supply your IAS3 credentials in environment variables in order to upload.
You can retrieve S3 keys from https://archive.org/account/s3.php

```python
>>> import os
>>> os.environ['AWS_ACCESS_KEY_ID']='x'
>>> os.environ['AWS_SECRET_ACCESS_KEY']='y'
>>> item = internetarchive.Item('new_identifier')
>>> item.upload('/path/to/image.jpg', dict(mediatype='image', creator='Jake Johnson'))
```

Item-level metadata must be supplied with the first file uploaded to an item.

You can upload additional files to an existing item:

```python
>>> item = internetarchive.Item('existing_identifier')
>>> item.upload('/path/to/image2.jpg')
```

### A note about mixed-case item names ###

The Internet Archive allows mixed-case item identifiers, but Amazon S3 does not allow
mixed-case bucket names. The `internetarchive` python module is built on top of the
`boto` S3 module. `boto` disallows creation of mixed-case buckets, but allows you to
download from existing mixed-case buckets. If you wish to upload a new item to the
Internet Archive with a mixed-case item identifier, you will need to monkey-patch
the `boto.s3.connection.check_lowercase_bucketname` function:

```python
>>> import boto
>>> def check_lowercase_bucketname(n):
...     return True

>>> boto.s3.connection.check_lowercase_bucketname = check_lowercase_bucketname

>>> item = internetarchive.Item('TestUpload_pythonapi_20130812')
>>> item.upload('file.txt', dict(mediatype='texts', creator='Internet Archive'))
True
```
