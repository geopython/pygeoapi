.. _ogcapi-processes:

Publishing processes via OGC API - Processes
============================================

`OGC API - Processes`_ provides geospatial data processing functionality in a standards-based
fashion (inputs, outputs).

pygeoapi implements OGC API - Processes functionality by providing a plugin architecture, thereby
allowing developers to implement custom processing workflows in Python.

The pygeoapi offers two processes: a default ``hello-world`` process which allows you to quickly explore the capabilities of processes, and an optional ``shapely-functions`` process with more advanced features that leverages `Shapely`_ to expose various geometric processing functionality.

Configuration
-------------

The below configuration is an example of a process defined within the pygeoapi internal plugin registry:

.. code-block:: yaml

   processes:
       # enabled by default
       hello-world:
           processor:
               name: HelloWorld

The below configuration is an example of a process defined as part of a custom Python process:

.. code-block:: yaml

   processes:
       # enabled by default
       hello-world:
           processor:
               # refer to a process in the standard PYTHONPATH
               # e.g. my_package/my_module/my_file.py (class MyProcess)
               # the MyProcess class must subclass from pygeoapi.process.base.BaseProcessor
               name: my_package.my_module.my_file.MyProcess

See :ref:`example-custom-pygeoapi-processing-plugin` for processing plugin examples.

Processing and response handling
--------------------------------

pygeoapi processing plugins must return a tuple of media type and native outputs.  Multipart
responses are not supported at this time, and it is up to the process plugin implementor to return a single
payload defining multiple artifacts (or references to them).

By default (or via the OGC API - Processes ``response: raw`` execution parameter), pygeoapi provides
processing responses in their native encoding and media type, as defined by a given
plugin (which needs to set the response content type and payload accordingly).

pygeoapi also supports a JSON-based response type (via the OGC API - Processes ``response: document``
execution parameter).  When this mode is requested, the response will always be a JSON encoding, embedding
the resulting payload (part of which may be Base64 encoded for binary data, for example).


Asynchronous support
--------------------

By default, pygeoapi implements process execution (jobs) as synchronous mode.  That is, when
jobs are submitted, the process is executed and returned in real-time.  Certain processes
that may take time to execute, or be delegated to a scheduler/queue, are better suited to
an asynchronous design pattern.  This means that when a job is submitted in asynchronous
mode, the server responds immediately with a reference to the job, which allows the client
to periodically poll the server for the processing status of a given job.

In keeping with the OGC API - Processes specification, asynchronous process execution
can be requested by including the ``Prefer: respond-async`` HTTP header in the request.

Job management is required for asynchronous functionality.

Job management
--------------

pygeoapi provides job management by providing a 'manager' concept which, well,
manages job execution.  The manager concept is implemented as part of the pygeoapi
:ref:`plugins` architecture.  pygeoapi provides a default manager implementation
based on `TinyDB`_ for simplicity.  Custom manager plugins can be developed for more
advanced job management capabilities (e.g. Kubernetes, databases, etc.).

Job managers
------------

TinyDB
^^^^^^

TinyDB is the default job manager for pygeoapi when enabled.

.. code-block:: yaml

   server:
       manager:
           name: TinyDB
           connection: /tmp/pygeoapi-process-manager.db
           output_dir: /tmp/

MongoDB
^^^^^^^

As an alternative to the default, a manager employing `MongoDB`_ can be used. 
The connection to a `MongoDB`_ instance must be provided in the configuration.
`MongoDB`_ uses ``localhost`` and port ``27017`` by default. Jobs are stored in a collection named
``job_manager_pygeoapi``.

.. code-block:: yaml

   server:
       manager:
           name: MongoDB
           connection: mongodb://host:port
           output_dir: /tmp/

PostgreSQL
^^^^^^^^^^

As another alternative to the default, a manager employing `PostgreSQL`_ can be used.
The connection to a `PostgreSQL`_ database must be provided in the configuration.
`PostgreSQL`_ uses ``localhost`` and port ``5432`` by default. Jobs are stored in a table named ``jobs``.

.. code-block:: yaml

   server:
       manager:
           name: PostgreSQL
           connection:
               host: localhost
               port: 5432
               database: test
               user: postgres
               password: ${POSTGRESQL_PASSWORD:-postgres}
           # Alternative accepted connection definition:
           # connection: postgresql://postgres:postgres@localhost:5432/test
           # connection: postgresql://postgres:${POSTGRESQL_PASSWORD:-postgres}@localhost:5432/test
           output_dir: /tmp


Putting it all together
-----------------------

To summarize how pygeoapi processes and managers work together:

* process plugins implement the core processing / workflow functionality
* manager plugins control and manage how processes are executed

Processing examples
-------------------

Hello World (Default)
^^^^^^^^^^^^^^^^^^^^^

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
       -H "Prefer: respond-async" \
       -d "{\"inputs\":{\"name\": \"hi there2\"}}"
   # execute a job for the ``hello-world`` process with a success subscriber
    curl -X POST http://localhost:5000/processes/hello-world/execution \
        -H "Content-Type: application/json" \
        -d "{\"inputs\":{\"name\": \"hi there2\"}, \
            \"subscriber\": {\"successUri\": \"https://www.example.com/success\"}}"

Shapely Functions (Optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `shapely-functions` process exposes some selected Shapely_ functions as sample process. The selection cut across different operations in Shapely. To avoid function collision, it uses the name of the function category as the namespace. E.g *union* operation under the *set* module is described as *set:union*.

The process is configured to accept a list of geometry *inputs* (WKT and/or GeoJSON geometry), *operation*  and an optional *output_format*. It performs the specified operation and returns the result in the specified *output_format* (If the operation does not return a geometry, then this is ignored).


Configuration
-------------

.. code-block:: yaml

   processes:
        shapely-functions:
           processor:
               name: ShapelyFunctions


**Supported operations**

* **measurement:bounds** - Computes the bounds (extent) of a geometry.
* **measurement:area** - Computes the area of a (multi)polygon.
* **measurement:distance** - Computes the Cartesian distance between two geometries.
* **predicates:covers** - Returns True if no point in geometry B is outside geometry A.
* **predicates:within** - Returns True if geometry A is completely inside geometry B.
* **set:difference** - Returns the part of geometry A that does not intersect with geometry B.
* **set:union** - Merges geometries into one.
* **constructive:buffer** - Computes the buffer of a geometry for positive and negative buffer distance.
* **constructive:centroid** - Computes the geometric center (center-of-mass) of a geometry.
 
**Limitation**

There is no support for passing optional function arguments yet. E.g when computing buffer on a geometry, no option to pass in the buffer distance.

.. code-block:: sh

   # describe the ``shapely-functions`` process
   curl http://localhost:5000/processes/shapely-functions

   # execute a job for the ``shapely-functions`` process that computes the bounds of a WKT
   curl -X POST http://localhost:5000/processes/shapely-functions/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"operation\": \"measurement:bounds\",\"geoms\": [\"POINT(83.27651071580385 22.593553859283745)\"]}}"

   # execute a job for the ``shapely-functions`` process that calculates the area of a WKT Polygon 
   curl -X POST http://localhost:5000/processes/shapely-functions/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"operation\": \"measurement:area\",\"geoms\": [\"POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))\"]}}"
   
   # execute a job for the ``shapely-functions`` process that calculates the distance between two WKTs
   curl -X POST http://localhost:5000/processes/shapely-functions/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"operation\": \"measurement:distance\",\"geoms\": [\"POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))\",\"POINT(83.27651071580385 22.593553859283745)\"]}}"
   
   # execute a job for the ``shapely-functions`` process that calculates the predicate difference between two WKTs and returns a GeoJSON feature
   curl -X POST http://localhost:5000/processes/shapely-functions/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"operation\": \"set:difference\",\"geoms\": [\"POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))\",\"POINT(83.27651071580385 22.593553859283745)\"],\"output_format\":\"geojson\"}}"
   
   # execute a job for the ``shapely-functions`` process that calculates the predicate difference between two WKTs and returns a WKT
   curl -X POST http://localhost:5000/processes/shapely-functions/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"operation\": \"set:difference\",\"geoms\": [\"POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))\",\"POINT(83.27651071580385 22.593553859283745)\"],\"output_format\":\"wkt\"}}"

   # execute a job for the ``shapely-functions`` process that computes the buffer of a GeoJSON feature and returns a WKT 
   curl -X POST http://localhost:5000/processes/shapely-functions/execution \
       -H "Content-Type: application/json" \
       -d "{\"inputs\":{\"operation\": \"constructive:buffer\",\"geoms\": [{\"type\": \"LineString\",\"coordinates\": [[102.0,0.0],[103.0, 1.0],[104.0,0.0]]}],\"output_format\":\"wkt\"}}"


.. _`OGC API - Processes`: https://ogcapi.ogc.org/processes
.. _`sample`: https://github.com/geopython/pygeoapi/blob/master/pygeoapi/process/hello_world.py
.. _`shapely_functions`: https://github.com/geopython/pygeoapi/blob/master/pygeoapi/process/shapely_functions.py
.. _`TinyDB`: https://tinydb.readthedocs.io/en/latest
.. _`Shapely`: https://shapely.readthedocs.io/
