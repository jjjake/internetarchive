.. _jq:

Using jq with ia
================

`jq <https://stedolan.github.io/jq/>`_ is a lightweight and flexible command-line JSON processor.
It's a great tool for processing the JSON output of ``ia``.
This document will go over how to install or download ``jq`` and how to use it with ``ia``.

If you have a tip you'd like to add to this page, please email `jake@archive.org <mailto:jake@archive.org>`_ or send a pull request.
If you're unable to figure out a ``jq`` command to do what you need and don't see it on this page, please email  `jake@archive.org <mailto:jake@archive.org>`_ for help.

Installation
------------

Downloading a binary
^^^^^^^^^^^^^^^^^^^^

The easiest way to get started with ``jq`` is to download a binary.
Binaries for Linux, OS X, and Windows are available at `https://stedolan.github.io/jq/download/ <https://stedolan.github.io/jq/download/>`_.
Once you find the binary for your OS, you could right-click the hypertext and copy the link to the binary.
Then you could paste it into your terminal and download it like so:

.. code:: bash

    $ curl -Ls https://github.com/stedolan/jq/releases/download/jq-1.5/jq-osx-amd64 > jq
    $ chmod +x jq  # make it executable

To confirm it's working, simply run the following.
You should see the help page.

.. code:: bash

    $ ./jq
    jq - commandline JSON processor [version 1.5]
    Usage: ./jq [options] <jq filter> [file...]
    
        jq is a tool for processing JSON inputs, applying the
        given filter to its JSON text inputs and producing the
        filter's results as JSON on standard output.
        The simplest filter is ., which is the identity filter,
        copying jq's input to its output unmodified (except for
        formatting).
        For more advanced filters see the jq(1) manpage ("man jq")
        and/or https://stedolan.github.io/jq
    
        Some of the options include:
         -c        compact instead of pretty-printed output;
         -n        use `null` as the single input value;
         -e        set the exit status code based on the output;
         -s        read (slurp) all inputs into an array; apply filter to it;
         -r        output raw strings, not JSON texts;
         -R        read raw strings, not JSON texts;
         -C        colorize JSON;
         -M        monochrome (don't colorize JSON);
         -S        sort keys of objects on output;
         --tab    use tabs for indentation;
         --arg a v    set variable $a to value <v>;
         --argjson a v    set variable $a to JSON value <v>;
         --slurpfile a f    set variable $a to an array of JSON texts read from <f>;
        See the manpage for more options.

Just like the ``ia`` binary, downloading the ``jq`` binary does not install it to your system.
It's simply an executable binary.
To use it, you'll have to use either a relative or absolute path. For example:

.. code:: bash

    $ ~/jq --help
    $ ./jq --help
    $ /Users/jake/jq --help

Installing with a package manager
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``jq`` can also be installed with most popular package managers:

.. code:: bash

    # Linux
    $ sudo apt-get install jq

    # OS X
    $ brew install jq

    # FreeBSD
    $ pkg install jq 

    # Solaris
    $ pkgutil -i jq

    # Windows
    $ chocolately install jq

Please refer to `https://stedolan.github.io/jq/download/ <https://stedolan.github.io/jq/download/>`_ for more details.



Getting started
---------------

``jq`` can seem a bit overwhelming at first, so let's get started with some basic examples.
A good way to make sense of how you can access a specific metadata field is to use ``jq 'keys'``.
This will show you the top-level keys that exist in the JSON document.

.. code:: bash

    $ ia metadata nasa | jq 'keys'
    [
      "created",
      "d1",
      "d2",
      "dir",
      "files",
      "files_count",
      "is_collection",
      "item_size",
      "metadata",
      "reviews",
      "server",
      "uniq",
      "workable_servers"
    ]

To access the value of a given key, you can simply do:

.. code:: bash

    $ ia metadata nasa | jq '.files_count'
    8

As you can see, the command above returns the value for the ``files_count`` key.
There are 8 files in the item.

When working with ``ia metadata`` the ``metadata`` and ``files`` keys are likely to be the targets you'll want to access most.
Let's take a look at ``metadata``:

.. code:: bash

    $ ia metadata | jq '.metadata | keys'
    [
      "addeddate",
      "backup_location",
      "collection",
      "description",
      "hidden",
      "homepage",
      "identifier",
      "mediatype",
      "num_recent_reviews",
      "num_subcollections",
      "num_top_dl",
      "publicdate",
      "related_collection",
      "rights",
      "show_browse_by_date",
      "show_hidden_subcollections",
      "show_search_by_year",
      "spotlight_identifier",
      "title",
      "updatedate",
      "updater",
      "uploader"
    ]

As you might notice, this is all of the item-level metadata (i.e. the JSON equivalent of an item's ``<identifier>_meta.xml`` file).
We can decend deeper into the JSON document like so:

.. code:: bash

    $ ia metadata nasa | jq '.metadata.title'
    "NASA Images"

``jq`` returns JSON by default.
In this case, a quoted string.
To access the raw value, you can use the ``-r`` option:

.. code:: bash

    $ ia metadata nasa | jq -r '.metadata.title'
    NASA Images

Search
------

``ia search`` outputs JSONL.
JSONL is series of JSON documents separated by a newline.
In this case, one JSON document is returned per search document reutrned.


Converting search results to CSV and other formats
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``jq`` can be used to parse the JSON returned by ``ia search`` into CSV or TSV files:

.. code:: bash

    $ ia search 'identifier:nasa OR identifier:stairs' --field title,date,subject | jq -r '[.identifier, .title, .date, .subject] | @csv'
    "nasa","NASA Images",,
    "stairs","stairs where i worked","2004-01-01T00:00:00Z","test"

If you'd prefer a tab-separated spreadsheet, you can replace ``@csv`` with ``@tsv`` in the command above.
More options can be found in the *Format strings and escaping* section in the `jq manual <https://stedolan.github.io/jq/manual/>`_.

Catalog
-------

Get info on all of your IA-S3 tasks:

.. code:: bash

    $ ia tasks --json | jq 'select(.args.comment == "s3-put")'

Or, output a link to the tasklog for each S3 task you currently have queued or running:

.. code:: bash

    $ ia tasks nasa --json \
        | jq -r 'select(.args.comment == "s3-put") | "https://archive.org/log/\(.task_id)"'
    https://archive.org/log/469558161
    https://archive.org/log/400818482

Get the identifiers for all of your redrows:

.. code:: bash

    $ ia tasks --json | jq -r 'select(.row_type == "red").identifier'

TODO
____

Recipes to document, work in progress...


Select files of a specific format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    $ ia metadata nasa | jq '.files[] | select(.format == "JPEG")'
    {
      "name": "globe_west_540.jpg",
      "source": "original",
      "size": "66065",
      "format": "JPEG",
      "mtime": "1245274910",
      "md5": "9366a4b09386bf673c447e33d806d904",
      "crc32": "2283b5fd",
      "sha1": "3e20a009994405f535cdf07cdc2974cef2fce8f2",
      "rotation": "0"
    }

Select a file by name
^^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    $ ia metadata nasa | jq '.files[] | select(.name == "nasa_meta.xml")'
    {
      "name": "nasa_meta.xml",
      "source": "metadata",
      "size": "7968",
      "format": "Metadata",
      "mtime": "1530756295",
      "md5": "06cd95343d60df0f10fb8518b349a795",
      "crc32": "6b9c6e24",
      "sha1": "c0dc994eeba245671ef53e2f6c52612722bf51d3"
    }


Get the size of a collection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    » ia search 'collection:georgeblood' -f item_size | jq '.item_size' | paste -sd+ - | bc
    51677834206186

Getting checksums for all files in an item
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    $ ia metadata nasa | jq -r '.metadata.identifier as $id | .files[] | [$id, .name, .md5] | @tsv'
    nasa    NASAarchiveLogo.jpg    64dcc1092df36142eb4aab7cc255a4a6
    nasa    __ia_thumb.jpg    c354f821954f80516d163c23135e7dd7
    nasa    globe_west_540.jpg    9366a4b09386bf673c447e33d806d904
    nasa    globe_west_540_thumb.jpg    d3dab682c56058c8af0df5a2073b1dd1
    nasa    nasa_archive.torrent    70a7b2b44c318bac381c25febca3b2ca
    nasa    nasa_files.xml    5b8a61ea930ce04d093deebe260fd5f8
    nasa    nasa_meta.xml    06cd95343d60df0f10fb8518b349a795
    nasa    nasa_reviews.xml    711ba65d49383a25657640716c45e840

Creating histograms
^^^^^^^^^^^^^^^^^^^

This example creates a histogram of publisher's grouped by item_size.

.. code:: bash

    » ia search 'collection:georgeblood' -f publisher,item_size \
        | jq -r '"\(.publisher) \(.item_size)"' \
        | awk '{arr[$1]+=$2} END {for (i in arr) {print i,arr[i]}}' \
        | sort -rn -k2 \
        | head
    Decca 9518737758200
    Victor 8067854677756
    Columbia 7221975357654
    Capitol 1944338651172
    Brunswick 1574280922547
    Bluebird 1058465142211
    Mercury 1003001910967
    MGM 898067089555
    Okeh 808308437878
    Vocalion 608766709327

Get total imagecount of a collection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: bash

    $ ia search 'scanningcenter:uoft AND shiptracking:ace54704' -f imagecount | jq '.imagecount' | paste -sd+ - | bc
    8172

Selecting files based on filesize
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Get the filenames of every file in ``goodytwoshoes00newyiala`` that is larger than 3000 bytes:

.. code:: bash

    $ ia metadata goodytwoshoes00newyiala \
        | jq -r '.files[] | select(.name | endswith(".pdf")) | select((.size | tonumber) > 3000) | .name'
    goodytwoshoes00newyiala.pdf
    goodytwoshoes00newyiala_bw.pdf

You can also include the identifier in the output like so:

.. code:: bash

    $ ia metadata goodytwoshoes00newyiala \
        | jq -r '.metadata.identifier as $i | .files[] | select(.name | endswith(".pdf")) | select((.size | tonumber) > 3000) | "\($i)/\(.name)"'
    goodytwoshoes00newyiala/goodytwoshoes00newyiala.pdf
    goodytwoshoes00newyiala/goodytwoshoes00newyiala_bw.pdf
