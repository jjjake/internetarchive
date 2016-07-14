Internet Archive Metadata
=========================

`Metadata <https://en.wikipedia.org/wiki/Metadata>`_ is data about data.
In the case of Internet Archive items, the metadata describes the contents of the items.
Metadata can include information such as the performance date for a concert, the name of the artist, and a set list for the event.

Metadata is a very important element of items in the Internet Archive.
Metadata allows people to locate and view information.
Items with little or poor metadata may never be seen and can become lost.


Archive.org Identifiers
-----------------------

Each item at Internet Archive has an identifier. An identifier is composed of any unique combination of alphanumeric characters, underscore (``_``) and dash (``-``). While there are no official limits it is strongly suggested that identifiers be between 5 and 80 characters in length.

Identifiers must be unique across the entirety of Internet Archive, not simply unique within a single collection.

Once defined an identifier **can not** be changed. It will travel with the item or object and is involved in every manner of accessing or referring to the item.


Standard Internet Archive Metadata Fields
-----------------------------------------

There are several standard metadata fields recognized for Internet Archive items.
Most metadata fields are optional.

addeddate
^^^^^^^^^

Contains the date on which the item was added to Internet Archive.

Please use an `ISO 8601 <https://en.wikipedia.org/wiki/ISO_8601>`_ compatible format for this date.
For instance, these are all valid date formats:

- YYYY
- YYYY-MM-DD
- YYYY-MM-DD HH:MM:SS

While it is possible to set the ``addeddate`` metadata value it is not recommended.
This value is typically set by automated processes.

adder
^^^^^

The name of the account which added the item to the Internet Archive.

While is is possible to set the ``adder`` metadata value it is not recommended.
This value is typically set by automated processes.

collection
^^^^^^^^^^

A collection is a specialized item used for curation and aggregation of other items.
Assigning an item to a collection defines where the item may be located by a user browsing Internet Archive.

A collection **must** exist prior to assigning any items to it.
Currently collections can only be created by Internet Archive staff members.
Please `contact Internet Archive <mailto:info@archive.org?subject=[Collection Creation Request]>`_ if you need a collection created.

All items **should** belong to a collection.
If a collection is not specified at the time of upload, it will be added to the ``opensource`` collection.
For testing purposes, you may upload to the ``test_collection`` collection.

contributor
^^^^^^^^^^^

The value of the ``contributor`` metadata field is information about the entity responsible for making contributions to the content of the item.
This is often the library, organization or individual making the item available on Internet Archive.

The value of this metadata field may contain HTML. ``<script>`` tags and CSS are not allowed.

coverage
^^^^^^^^

The extent or scope of the content of the material available in the item.
The value of the ``coverage`` metadata field may include geographic place, temporal period, jurisdiction, etc.
For items which contain multi-volume or serial content, place the statement of holdings in this metadata field.

creator
^^^^^^^

An entity primarily responsible for creating the files contained in the item.

credits
^^^^^^^

The participants in the production of the materials contained in the item.

The value of this metadata field may contain HTML. ``<script>`` tags and CSS are not allowed.

date
^^^^

The publication, production or other similar date of this item. 

Please use an `ISO 8601 <https://en.wikipedia.org/wiki/ISO_8601>`_ compatible format for this date.

description
^^^^^^^^^^^

A description of the item.

The value of this metadata field may contain HTML. ``<script>`` tags and CSS are not allowed.

language
^^^^^^^^

The primary language of the material available in the item.

While the value of the ``language`` metadata field can be any value, Internet Archive prefers they be `MARC21 Language Codes <https://www.loc.gov/marc/languages/language_name.html>`_.

licenseurl
^^^^^^^^^^

A URL to the license which covers the works contained in the item.

Internet Archive recommends (but does not require) `Creative Commons <https://creativecommons.org>`_ licensing.
Creative Commons provides a `license selector <https://creativecommons.org/choose/?partner=ia&exit_url=http%3A%2F%2Fwww.archive.org%2Fservices%2Flicense-chooser.php%3Flicense_url%3D%5Blicense_url%5D%26license_name%3D%5Blicense_name%5D%26license_image%3D%5Blicense_button%5D%26deed_url%3D%5Bdeed_url%5D&jurisdiction_choose=1>`_ for finding the correct license for your needs.

mediatype
^^^^^^^^^

The primary type of media contained in the item.
While an item can contain files of diverse mediatypes the value in this field defines the appearance and functionality of the item's detail page on Internet Archive.
In particular, the mediatype of an item defines what sort of online viewer is available for the files contained in the item.

The mediatype metadata field recognizes a limited set of values:

- ``audio``: The majority of audio items should receive this mediatype value.
  Items for the `Live Music Archive <https://www.archive.org/details/etree>`_ should instead use the ``etree`` value.
- ``collection``: Denotes the item as a collection to which other collections and items can belong. 
- ``data``: This is the default value for mediatype.
  Items with a mediatype of ``data`` will be available in Internet Archive but you will not be able to browse to them.
  In addition there will be no online reader/player for the files.
- ``etree``: Items which contain files for the `Live Music Archive <https://www.archive.org/details/etree>`_ should have a mediatype value of ``etree``.
  The Live Music Archive has very specific upload requirements.
  Please consult the `documentation <https://www.archive.org/about/faqs.php#Live_Music_Archive>`_ for the Live Music Archive prior to creating items for it.
- ``image``: Items which predominantly consist of image files should receive a mediatype value of ``image``.
  Currently these items will not available for browsing or online viewing in Internet Archive but they will require no additional changes when this mediatype receives additional support in the Archive.
- ``movies``: All videos (television, features, shorts, etc.) should receive a mediatype value of ``movies``.
  These items will be displayed with an online video player.
- ``software``: Items with a mediatype of ``software`` are accessible to browse via Internet Archive's `software collection <http://www.archive.org/details/software>`_.
  There is no online viewer for software but all files are available for download.
- ``texts``: All text items (PDFs, EPUBs, etc.) should receive a mediatype value of ``texts``.
- ``web``: The ``web`` mediatype value is reserved for items which contain web archive `WARC <http://www.digitalpreservation.gov/formats/fdd/fdd000236.shtml>`_ files.

If the mediatype value you set is not in the list above it will be saved but ignored by the system. The item will be treated as though it has a mediatype value of ``data``.

If a value is not specified for this field it will default to ``data``.

noindex
^^^^^^^

All items will have their metadata included in the Internet Archive search engine.
To disable indexing in the search engine, include a ``noindex`` metadata tag.
The value of the tag does not matter.
Its presence is enough to trigger not including the metadata in the search engine.

If an item's metadata has already been indexed in the search engine, setting ``noindex`` will remove it from the index.

Items whose metadata is not not included in the search engine index are not considered "public" per se and therefore will not have a value in the ``publicdate`` metadata field (see below).

notes
^^^^^

Contains user-defined information about the item.

The value of this metadata field may contain HTML. ``<script>`` tags and CSS are not allowed.

pick
^^^^

On the v1 archive.org site, each collection page on Internet Archive may include a "Staff Picks" section.
This section will highlight a single item in the collection.
This item will be selected at random from the items with a ``pick`` metadata value of ``1``.
If there are no items with this ``pick`` metadata value the "Staff Picks" section will not appear on the collection page.

By default all new items have no `pick` metadata value.
**Note:** v2 of the archive.org website does not make use of this value.

publicdate
^^^^^^^^^^

Items which have had their metadata included in the Internet Archive search engine index are considered to be public.
The date the metadata is added to the index is the public date for the item.

Please use an `ISO 8601 <https://en.wikipedia.org/wiki/ISO_8601>`_ compatible format for this date.
For instance, these are all valid date formats:

While it is possible to set the ``publicdate`` metadata value it is not recommended.
This value is typically set by automated processes.

publisher
^^^^^^^^^

The publisher of the material available in the item.

rights
^^^^^^

A statement of the rights held in and over the files in the item.

The value of this metadata field may contain HTML. ``<script>`` tags and CSS are not allowed.

subject
^^^^^^^

Keyword(s) or phrase(s) that may be searched for to find your item.
This field can contain multiple values:

.. code:: bash

    $ ia metadata <identifier> --modify='subject:foo' --modify='subject:bar'

Or, in Python:

.. code:: python

    >>> from internetarchive import modify_metadata
    >>> md = dict(subject=['foo', 'bar'])
    >>> r = modify_metadata('<identifier>', md)

It is helpful but **not** necessary for you to use `Library of Congress Subject Headings <http://id.loc.gov/authorities/subjects.html>`_ for the value of this metadata header.

title
^^^^^

The title for the item.
This appears in the header of the item's detail page on Internet Archive.

If a value is not specified for this field it will default to the identifier for the item.

updatedate
^^^^^^^^^^

The date on which an update was made to the item.
This field is repeatable.

Please use an `ISO 8601 <http://en.wikipedia.org/wiki/ISO_8601>`_ compatible format for this date.

While it is possible to set the ``publicdate`` metadata value it is not recommended.
This value is typically set by automated processes.

updater
^^^^^^^

The name of the account which updated the item.
This field is repeatable.

While it is possible to set the ``updater`` metadata value it is not recommended.
This value is typically set by automated processes.

uploader
^^^^^^^^

The name of the account which uploaded the file(s) to the item.

The uploader has ownership over the item and is allowed to maintain it.

This value is set by automated processes.


Custom Metadata Fields
----------------------

Internet Archive strives to be metadata agnostic, enabling users to define the metadata format which best suits the needs of their material.
In addition to the standard metadata fields listed above you may also define as many custom metadata fields as you require.
These metadata fields can be defined ad hoc at item creation or metadata editing time and do not have to be defined in advance.
