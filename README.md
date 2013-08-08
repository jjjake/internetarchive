## A python interface to archive.org ##

The Internet Archive stores data in "items". You can query the archive using an item identifier:

```python
>>> import archive
>>> item = archive.Item('stairs')
>>> print item.metadata
```

Items contains files, which can be downloaded:

```python
>>> file = item.file('glogo.png')
>>> file.download() #writes to disk
>>> f.download('/foo/bar/some_other_name.png')
```

You can iterate over files:

```python
>>> for f in item.files():
...     print f.name, f.sha1
```

You can use the IA's S3-like interface to upload files to an item.
You need to supply your IAS3 credentials in environment variables in order to upload.
You can retrieve S3 keys from https://archive.org/account/s3.php

```python
>>> import os;
>>> os.environ['AWS_ACCESS_KEY_ID']='x'; os.environ['AWS_SECRET_ACCESS_KEY']='y'
>>> item.upload('myfile')
True
```
