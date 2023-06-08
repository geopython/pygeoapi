.. _running:

Running
=======

Since pygeoapi is a Python API at its core, it can be served via numerous web server scenarios. 
So far, pygeoapi can be served via Flask `WSGI`_, Starlette `ASGI`_, and `Django`_.

This section covers how pygeoapi can be run in development environments and in production environments. 
For running pygeoapi using docker, refer to the :ref:`running-with-docker` section.

Running in development
----------------------

The ``pygeoapi serve`` is the easiest way to run pygeoapi in your own machine.
This command starts a pygeoapi server instance. By default, a Flask server is started, 
but Starlette and Django are available as well.

Using the ``--starlette`` or ``--django`` flags will start pygeoapi using the specified server technology.

It is also advisable to install the development dependencies (contained in the requirements-dev.txt file) for running pygeoapi for 
development. To do so, run the following command:

.. code-block:: bash

   pip3 install -r requirements-dev.txt

.. note::
   * Changes to the configuration files of pygeoapi or OpenAPI requires a server restart (configurations are loaded once at server startup for performance).

   * Changes to the codebase require a rebuild (i.e., re-running the ``python3 setup.py install`` command). For instructions for running pygeoapi with hot-reloading, refer to the "Hot-reloading" section.

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

To use Starlette as the web server it is necessary to install its dependencies running the following command:

.. code-block:: bash

   pip3 install -r requirements-starlette.txt

Then, the Starlette ASGI server can be run as follows:

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

Django
^^^^^^

`Django`_ is a Python web framework that encourages rapid development and clean, pragmatic design. 

Similarly to Flask and Starlette, Django can be used by pygeoapi to communicate with the core API.

.. code-block:: bash

   HTTP request <--> Django (pygeoapi/django_app.py) <--> pygeoapi API (pygeoapi/api.py)

To use Django as a web server it is necessary to install its dependencies running the following command:

.. code-block:: bash

   pip3 install -r requirements-django.txt

After Django rependencies is installed, pygeoapi can be run as follows: 

.. code-block:: bash

    pygeoapi serve --django

As a result, your Django application will be available at http://localhost:5000/.


To integrate pygeoapi as part of another Django project in a pluggable it is necessary to add the pygeoapi urls to the 
main Django application urls:

.. code-block:: python

   from django.contrib import admin
   from django.urls import path, include

   from pygeoapi.django_pygeoapi import urls as pygeoapi_urls

   urlpatterns = [
      path('admin/', admin.site.urls),
      path('sample-project/', include(pygeoapi_urls)),
   ]


This integration can be seen in the provided example Django project. Refer to `examples/django/sample_project/README.md` 
for the integration of pygeoapi with an already exising Django application.

Hot-reloading
^^^^^^^^^^^^^

The ``pygeoapi serve`` uses the current pygeoapi installation. If the installation was performed using the setup command 
provided in the :ref:`install` section (``python3 setup.py install``), changes made to the codebase of pygeoapi are not going to be 
reflected in the application until a rebuild (i.e., re-running ``python3 setup.py install``).

By hot-reloading we mean to be able to directly see changes reflected in the application without reinstalling the pygeoapi package or resetting the server. 
This is useful for development, as the changes made by developers are easily and rapidly reflected and they can take advantage 
of the hot-reloading capabilities that offer each of the web servers available.

For enabling hot-reloading, install the pygeoapi package using pip (instead of the setup.py script) with the following command: 

.. code-block:: bash

   pip3 install -e .

.. note::
   This command must be run from the root directory of pygeoapi. 

After the local package is built, you can use the ``pygeoapi serve`` 
again and the changes on the codebase will be directly reflected on the running instance.


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
   Gunicorn is as easy to install as ``pip3 install gunicorn``

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

Running Gunicorn with Starlette requires the `Uvicorn`_ library, which provides async capabilities along with Gunicorn.
Uvicorn includes a Gunicorn worker class allowing you to run ASGI applications, with all of Uvicorn's performance
benefits, while also giving you Gunicorn's fully-featured process management.

It is simple to run using the following command:

.. code-block:: bash

   gunicorn pygeoapi.starlette_app:app -w 4 -k uvicorn.workers.UvicornWorker

.. note::
   Uvicorn is as easy to install as ``pip3 install uvicorn``

Summary
-------

pygeoapi has many approaches for deploying depending on your requirements.  Choose one that works for you
and modify accordingly.

.. note::
   Additional approaches are welcome and encouraged; see :ref:`contributing` for more information on
   how to contribute to and improve the documentation


.. _`WSGI`: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface
.. _`ASGI`: https://asgi.readthedocs.io/en/latest
.. _`Gunicorn`: https://gunicorn.org
.. _`WSGI server list`: https://wsgi.readthedocs.io/en/latest/servers.html
.. _`Gunicorn settings`: https://docs.gunicorn.org/en/stable/settings.html
.. _`Uvicorn`: https://www.uvicorn.org
.. _`mod_wsgi`: https://modwsgi.readthedocs.io/en/master
.. _`Django`: https://www.djangoproject.com
