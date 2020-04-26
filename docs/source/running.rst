.. _running:

Running
=======

Now we are ready to start up pygeoapi.


``pygeoapi serve``
------------------

The ``pygeoapi serve`` command starts up an instance using Flask as the default server.  pygeoapi
can be served via Flask `WSGI`_ or Starlette `ASGI`_.

Since pygeoapi is a Python API at its core, it can be served via numerous web server scenarios.

.. note::
   Changes to either of the pygeoapi or OpenAPI configurations requires a server restart (configurations
   are loaded once at server startup for performance).


Flask WSGI
^^^^^^^^^^

Web Server Gateway Interface (WSGI) is a standard for how web servers communicate with Python applications.  By
having a WSGI server, HTTP requests are processed into threads/processes for better performance.  Flask is a WSGI
implementation which pygeoapi utilizes to communicate with the core API.

.. code-block:: bash

   HTTP request <--> Flask (pygeoapi/flask_app.py) <--> pygeoapi API (pygeoapi/api.py)


The Flask WSGI server can be run as follows:

.. code-block:: bash

   pygeoapi serve --flask
   pygeoapi serve  # uses Flask by default


Starlette ASGI
^^^^^^^^^^^^^^

Asynchronous Server Gateway Interface (ASGI) is standard interface between async-capable web servers, frameworks,
and applications written in Python.  ASGI provides the benefits of WSGI as well as asynchronous capabilities.
Starlette is an ASGI implementation which pygeoapi utilizes to communicate with the core API in asynchronous mode.

.. code-block:: bash

   HTTP request <--> Starlette (pygeoapi/starlette_app.py) <--> pygeoapi API (pygeoapi/api.py)


The Flask WSGI server can be run as follows:

.. code-block:: bash

   pygeoapi serve --starlette


Running in production
---------------------

Running ``pygeoapi serve`` in production is not recommended or advisable.  Preferred options are described below.

.. seealso::
   :ref:`running-with-docker` for container-based production installations.

Apache and mod_wsgi
^^^^^^^^^^^^^^^^^^^

Deploying pygeoapi via `mod_wsgi`_ provides a simple approach to enabling within Apache.

To deploy with mod_wsgi, your Apache instance must have mod_wsgi enabled within Apache.  At this point,
set up the following Python WSGI script:

.. code-block:: python

   import os

   os.environ['PYGEOAPI_CONFIG'] = '/path/to/my-pygeoapi-config.yml'
   os.environ['PYGEOAPI_OPENAPI'] = '/path/to/my-pygeoapi-openapi.yml'

   from pygeoapi.flask_app import APP as application

Now configure in Apache:

.. code-block:: apache

   WSGIDaemonProcess pygeoapi processes=1 threads=1
   WSGIScriptAlias /pygeoapi /path/to/pygeoapi.wsgi process-group=pygeoapi application-group=%{GLOBAL}

   <Location /pygeoapi>
     Header set Access-Control-Allow-Origin "*"
   </Location>

Gunicorn
^^^^^^^^

`Gunicorn`_ (for UNIX) is one of several Python WSGI HTTP servers that can be used for production environments.

.. code-block:: bash

   HTTP request --> WSGI or ASGI server (gunicorn) <--> Flask or Starlette (pygeoapi/flask_app.py or pygeoapi/starlette_app.py) <--> pygeoapi API

.. note::
   Gunicorn is as easy to install as ``pip install gunicorn``

.. note::
   For a complete list of WSGI server implementations, see the `WSGI server list`_.


Gunicorn and Flask
^^^^^^^^^^^^^^^^^^

Gunicorn and Flask is simple to run:

.. code-block:: bash

   gunicorn pygeoapi.flask_app:APP

.. note::
   For extra configuration parameters like port binding, workers, and logging please consult the `Gunicorn settings`_.


Gunicorn and Starlette
^^^^^^^^^^^^^^^^^^^^^^

Running Gunicorn with Starlette requires the `Uvicorn`_ which provides async capabilities along with Gunicorn.
Uvicorn includes a Gunicorn worker class allowing you to run ASGI applications, with all of Uvicorn's performance
benefits, while also giving you Gunicorn's fully-featured process management.

is simple to run from the command, e.g:

.. code-block:: bash

   gunicorn pygeoapi.starlette_app:app -w 4 -k uvicorn.workers.UvicornWorker

.. note::
   Uvicorn is as easy to install as ``pip install guvicorn``

Summary
-------

pygeoapi has many approaches for deploying depending on your requirements.  Choose one that works for you
and modify accordingly.

.. note::
   Additional approaches are welcome and encouraged; see :ref:`contributing` for more information on
   how to contribute to and improve the documentation


.. _`WSGI`: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface
.. _`ASGI`: https://asgi.readthedocs.io
.. _`Gunicorn`: https://gunicorn.org
.. _`WSGI server list`: https://wsgi.readthedocs.io/en/latest/servers.html
.. _`Gunicorn settings`: http://docs.gunicorn.org/en/stable/settings.html
.. _`Uvicorn`: https://www.uvicorn.org
.. _`mod_wsgi`: https://modwsgi.readthedocs.io
