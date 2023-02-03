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

To integrate pygeoapi as part of another Flask application, use Flask blueprints:

.. code-block:: python

   from flask import Flask
   from pygeoapi.flask_app import BLUEPRINT as pygeoapi_blueprint

   app = Flask(__name__)

   app.register_blueprint(pygeoapi_blueprint, url_prefix='/oapi')


   @app.route('/')
   def hello_world():
       return 'Hello, World!'


As a result, your application will be available at http://localhost:5000/ and pygeoapi will be available
at http://localhost:5000/oapi

Starlette ASGI
^^^^^^^^^^^^^^

Asynchronous Server Gateway Interface (ASGI) is standard interface between async-capable web servers, frameworks,
and applications written in Python.  ASGI provides the benefits of WSGI as well as asynchronous capabilities.
Starlette is an ASGI implementation which pygeoapi utilizes to communicate with the core API in asynchronous mode.

.. code-block:: bash

   HTTP request <--> Starlette (pygeoapi/starlette_app.py) <--> pygeoapi API (pygeoapi/api.py)


The Starlette ASGI server can be run as follows:

.. code-block:: bash

   pygeoapi serve --starlette

To integrate pygeoapi as part of another Starlette application:


.. code-block:: python

   from starlette.applications import Starlette
   from starlette.responses import PlainTextResponse
   from starlette.routing import Route
   from pygeoapi.starlette_app import app as pygeoapi_app


   async def homepage(request):
       return PlainTextResponse('Hello, World!')

   app = Starlette(debug=True, routes=[
       Route('/', homepage),
   ])

   app.mount('/oapi', pygeoapi_app)


As a result, your application will be available at http://localhost:5000/ and pygeoapi will be available
at http://localhost:5000/oapi

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


When running pygeoapi in a Python virtual environment, use directives similar to the below:

.. code-block:: apache

   WSGIDaemonProcess pygeoapi processes=1 threads=1 python-home=/path/to/venv/pygeoapi
   WSGIScriptAlias /pygeoapi /path/to/pygeoapi.wsgi process-group=pygeoapi application-group=%{RESOURCE}


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
   Uvicorn is as easy to install as ``pip install uvicorn``


Django
^^^^^^

`Django`_ is a Python web framework that encourages rapid development and clean, pragmatic design.  Assuming
a Django install/enabled application:


.. code-block:: bash

    pygeoapi serve --django


To integrate pygeoapi as part of another Django project in a pluggable way the truly impatient developers can
see `examples/django/sample_project/README.md` for a complete Django application.

As a result, your Django application will be available at http://localhost:5000/ and pygeoapi will be available
at http://localhost:5000/oapi


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
.. _`Django`: https://djangoproject.com
