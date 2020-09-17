Using GNU Parallel with ia
==========================

`GNU Parallel <https://www.gnu.org/software/parallel/>`_ is a shell tool for executing jobs in parallel.
It is a very useful tool to use with ``ia`` for bulk jobs.
It can be installed via many OS package managers.

For example, it can be installed via `homebrew <https://brew.sh/>`_ on Mac OS::

    brew install parallel

Refer to the `GNU Parallel homepage <https://www.gnu.org/software/parallel/>`_ for more details on available packaes, source code, installation, and other documentation and tutorials.


Basic Usage
-----------

You can use ``parallel`` to retrieve metadata from archive.org items concurrently:

.. code:: bash

    $ cat itemlist.txt
    jj-test-2020-09-17-1
    jj-test-2020-09-17-2
    jj-test-2020-09-17-3
    $ cat itemlist.txt | parallel 'ia metadata {}' | jq .metadata.date
    "1999"
    "1999"
    "1999"

You can run ``parallel`` with ``--dry-run`` to check your commands before running them:

.. code:: bash

    $ cat itemlist.txt | parallel --dry-run 'ia metadata {}'
    ia metadata jj-test-2020-09-17-2
    ia metadata jj-test-2020-09-17-1
    ia metadata jj-test-2020-09-17-3

Logging and retrying with Parallel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Parallel also offers an easy way to log and retry failed commands.

Here's an example of a job that is retrieving metadata for all of the items in the file named ``itemlist.txt``, and outputing the metadata to a file named ``output.jsonl``.
It uses the ``--joblog`` option to log all commands and their exit value to ``/tmp/my_ia_job.log``:

.. code:: bash

    $ cat itemlist.txt | parallel --joblog /tmp/my_ia_job.log 'ia metadata {}' > output.jsonl

You can now retry any commands that failed by using the ``--retry-failed`` option (don't forget to switch ``>`` to ``>>`` in this example, so you don't overwrite ``output.jsonl``! ``>>`` means to append to the output file, rather than clobber it):

.. code:: bash

    $ parallel --retry-failed --joblog /tmp/my_ia_job.log 'ia metadata {}' >> output.jsonl

If there were no failed commands, nothing will be rerun.
You can rerun this command until it exits with ``0``.
You can check the exit code by running ``echo $?`` directly after the ``parallel`` command finishes.
