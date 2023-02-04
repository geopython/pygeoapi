.. _ogcapi-processes:

Publishing processes via OGC API - Processes
============================================

`OGC API - Processes`_ provides geospatial data processing functionality in a standards-based
fashion (inputs, outputs).

pygeoapi implements OGC API - Processes functionality by providing a plugin architecture, thereby
allowing developers to implement custom processing workflows in Python.

A `sample`_ ``hello-world`` process is provided with the pygeoapi default configuration.

Configuration
-------------

.. code-block:: yaml

   processes:
       hello-world:
           processor:
               name: HelloWorld

Asynchronous support
--------------------

By default, pygeoapi implements process execution (jobs) as synchronous mode.  That is, when
jobs are submitted, the process is executed and returned in real-time.  Certain processes
that may take time to execute, or be delegated to a scheduler/queue, are better suited to
an asynchronous design pattern.  This means that when a job is submitted in asynchronous
mode, the server responds immediately with a reference to the job, which allows the client
to periodically poll the server for the processing status of a given job.

pygeoapi provides asynchronous support by providing a 'manager' concept which, well,
manages job execution.  The manager concept is implemented as part of the pygeoapi
:ref:`plugins` architecture.  pygeoapi provides a default manager implementation
based on `TinyDB`_ for simplicity.  Custom manager plugins can be developed for more
advanced job management capabilities (e.g. Kubernetes, databases, etc.).


.. code-block:: yaml

   server:
       manager:
           name: TinyDB
           connection: /tmp/pygeoapi-process-manager.db
           output_dir: /tmp/


Putting it all together
-----------------------

To summarize how pygeoapi processes and managers work together::

* process plugins implement the core processing / workflow functionality
* manager plugins control and manage how processes are executed

Processing examples
-------------------

* list all processes
  * http://localhost:5000/processes
* describe the ``hello-world`` process
  * http://localhost:5000/processes/hello-world
* show all jobs
  * http://localhost:5000/jobs
* execute a job for the ``hello-world`` process
  * ``curl -X POST "http://localhost:5000/processes/hello-world/execution" -H "Content-Type: application/json" -d "{\"inputs\":{\"name\": \"hi there2\"}}"``
* execute a job for the ``hello-world`` process with a raw response (default)
  * ``curl -X POST "http://localhost:5000/processes/hello-world/execution" -H "Content-Type: application/json" -d "{\"inputs\":{\"name\": \"hi there2\"}}"``
* execute a job for the ``hello-world`` process with a response document
  * ``curl -X POST "http://localhost:5000/processes/hello-world/execution" -H "Content-Type: application/json" -d "{\"inputs\":{\"name\": \"hi there2\"},\"response\":\"document\"}"``
* execute a job for the ``hello-world`` process in asynchronous mode
  * ``curl -X POST "http://localhost:5000/processes/hello-world/execution" -H "Content-Type: application/json" -d "{\"mode\": \"async\", \"inputs\":{\"name\": \"hi there2\"}}"``

.. todo:: add more examples once OAProc implementation is complete

.. _`OGC API - Processes`: https://ogcapi.ogc.org/processes
.. _`sample`: https://github.com/geopython/pygeoapi/blob/master/pygeoapi/process/hello_world.py
.. _`TinyDB`: https://tinydb.readthedocs.io/en/latest
