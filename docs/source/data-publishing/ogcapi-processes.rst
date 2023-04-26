.. _ogcapi-processes:

Publishing processes via OGC API - Processes
============================================

`OGC API - Processes`_ provides geospatial data processing functionality in a standards-based
fashion (inputs, outputs).

pygeoapi implements OGC API - Processes functionality by providing a plugin architecture, thereby
allowing developers to implement custom processing workflows in Python.

Two `sample`_ processes process are provided with the pygeoapi default configuration:

* ``HelloWorldProcessor`` - A simple process that takes one mandatory ``name`` input and an additional optional
  ``message`` input and produces an ``echo`` output, which is a string with a greeting that includes the provided
  name and message. The output is of type ``text/plain``.

* ``GreeterProcessor`` - A simple process that takes one mandatory ``num_greetings`` input and produces a ``greetings``
  output, which is a JSON object with a single ``greetings`` property - this property is a list of generated greetings.
  The output is of type ``application/json``.


Configuration
-------------

Processes are configured as normal resources in the pygeoapi configuration file. Their configuration follows the
following pattern:

.. code-block:: yaml

   resources:
       <process-id>:
           processor:
               name: <process-name | process-dotted-path>

Where ``<process-id>`` is replaced by the process identifier and ``processor.name`` and either be:

1. the process name, if it is known to pygeoapi, _i.e._ if this process is part of pygeoapi core
2. the process dotted path, for processes that are part of third-party Python packages which have already been installed

For example, this is the relevant configuration snippet that is included in pygeoapi's ``pygeoapi-config.yml``:

.. code-block:: yaml

   resources:
     hello-world:
       type: process
       processor:
         name: HelloWorld
     greeter:
       type: process
       processor:
         name: pygeoapi.process.hello_world.GreeterProcessor


These two sample processes specify a different ``processor.name``, in order to demo both options mentioned above


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

In keeping with the OGC API - Processes specification, asynchronous process execution
can be requested by including the ``Prefer: respond-async`` HTTP header in the request


.. code-block:: yaml

   server:
       manager:
           name: TinyDB
           connection: /tmp/pygeoapi-process-manager.db
           output_dir: /tmp/

MongoDB
--------------------
As an alternative to the default, pygeoapi also ships with a manager powered by `MongoDB`_.
The connection to an installed `MongoDB`_ instance must be provided in the configuration.
`MongoDB`_ uses the localhost and port 27017 by default. Jobs are stored in a collection named
job_manager_pygeoapi.

.. code-block:: yaml

   server:
       manager:
           name: MongoDB
           connection: mongodb://host:port
           output_dir: /tmp/


Putting it all together
-----------------------

To summarize how pygeoapi processes and managers work together::

* process plugins implement the core processing / workflow functionality
* manager plugins control and manage how processes are executed

Processing examples
-------------------

.. code-block:: sh

   # list all processes
   curl http://localhost:5000/processes

   # describe the ``hello-world`` process
   curl http://localhost:5000/processes/hello-world

   # show all jobs
   curl http://localhost:5000/jobs

   # execute a job for the ``hello-world`` process
   curl -X POST http://localhost:5000/processes/hello-world/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"name\": \"hi there2\"}}"

   # execute a job for the ``hello-world`` process with a raw response (default)
   curl -X POST http://localhost:5000/processes/hello-world/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"name\": \"hi there2\"}}"

   # execute a job for the ``hello-world`` process with a response document
   curl -X POST http://localhost:5000/processes/hello-world/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"name\": \"hi there2\"},\"response\":\"document\"}"

   # execute a job for the ``hello-world`` process in asynchronous mode
   curl -X POST http://localhost:5000/processes/hello-world/execution \
       -H "Content-Type: application/json" \
       -H "Prefer: respond-async"
       -d "{\"inputs\":{\"name\": \"hi there2\"}}"

.. todo:: add more examples once OAProc implementation is complete

.. _`OGC API - Processes`: https://ogcapi.ogc.org/processes
.. _`hello-world`: https://github.com/geopython/pygeoapi/blob/master/pygeoapi/process/hello_world.py
.. _`TinyDB`: https://tinydb.readthedocs.io/en/latest
