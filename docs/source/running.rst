.. _running:

Running
=======

Since pygeoapi is a Python API at its core, it can be served via numerous web server scenarios. 
So far, pygeoapi can be served via Flask `WSGI`_, Starlette `ASGI`_, and `Django`_.

This section covers how pygeoapi can be run in development environments and in production environments. 
For running pygeoapi using docker, refer to the :ref:`running-with-docker` section.


pygeoapi serve CLI command
--------------------------

Running pygeoapi as a standalone application can be done by using the ``pygeoapi serve`` CLI command. This command
starts a gunicorn web server and serves pygeoapi.
This command becomes available after you install pygeoapi. It can be used both for development (with the ``--debug``
flag) and production. In order to run, it needs to be made aware of the path to pygeoapi configuration file and the
path to pygeoapi's openapi document - these paths can be provided either as inputs to ``pygeoapi serve`` or as
environment variables:

.. code-block:: bash

   # either pass the config and openapi paths as arguments to pygeoapi serve
   pygeoapi \
       --pygeoapi-config /some/path/my-pygeoapi-config.yml \
       --pygeoapi-openapi /some/path/my-pygeoapi-openapi.yml \
       serve

   # or set them as environment variables and the call pygeoapi serve
   export PYGEOAPI_CONFIG=/some/path/my-pygeoapi-config.yml
   export PYGEOAPI_OPENAPI=/some/path/my-pygeoapi-openapi.yml
   pygeoapi serve

``pygeoapi serve`` also accepts a flag for each supported web framework to use as a base. This means you can call it
with ``--flask`` (the default), ``--django`` or ``starlette``.

It is also possible to pass extra arguments to gunicorn by appending them to the end of the ``pygeoapi serve`` command.
In order to make it clearer that these are arguments for gunicorn you may optionally use the ``--`` string before
specifying them - this is not mandatory though:

.. code-block:: bash

   # pass arguments to gunicorn like this
   pygeoapi serve -- --workers=4

   # this also works, but is not as clear
   pygeoapi serve --workers=4


Running in development
----------------------

In development you should provide the ``--debug`` flag to ``pygeoapi serve``. This flag will instruct the gunicorn
web server to:

- Use a single worker process, which makes it easier to attach a debugger
- Monitor the source code directory and automatically reload the worker process whenever the code changes
- Also monitor the pygeoapi configuration and openapi files and reload the worker process whenever thy change
- Use a log level of ``DEBUG``, regardless of what you may have set in your pygeoapi config file

It is also advisable to install the development dependencies (contained in the requirements-dev.txt file) for running pygeoapi for
development. To do so, run the following command:

.. code-block:: bash

   pip3 install -r requirements-dev.txt

.. note::

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

   # uses flask by default
   pygeoapi serve

   # you can also be explicit
   pygeoapi serve --flask


To integrate pygeoapi as part of another Flask application, use the provided pygeoapi Flask blueprint.

The pygeoapi flask blueprint expects to be able to find a ``PYGEOAPI`` key in the  flask app's ``config`` object. This
config key is expected to be a dictionary and to contain at least the following keys:

- ``api`` - This should store an instance of ``pygeoapi.api.API``

.. code-block:: python

   # my-custom-flask-app.py
   import flask

   import pygeoapi.util
   from pygeoapi.flask_app import BLUEPRINT as pygeoapi_blueprint
   from pygeoapi.api import API

   pygeoapi_config = pygeoapi.util.get_config_from_path(Path('example-config.yml'))
   pygeoapi_openapi = pygeoapi.util.get_openapi_from_path(Path('example-openapi.yml'))

   app = flask.Flask(__name__)
   app.config['PYGEOAPI'] = {
       'api': API(
           config=pygeoapi_config,
           openapi=pygeoapi_openapi,
       )
   }
   app.register_blueprint(pygeoapi_blueprint, url_prefix='/my-pygeoapi')

   @app.route('/')
   def hello_world():

       # inside a flask route you can retrieve the pygeoapi API object
       # from the app configuration
       pygeoapi_config = flask.current_app.config['PYGEOAPI']['api'].config
       description = pygeoapi_config['metadata']['identification']['title']['en']
       return (
           f'<h1>Hi this is a pygeoapi-enabled flask app</h1>'
           f'<p>Oh, and the pygeoapi server description is: {description}</p>'
       )


The application above can be run, for example, with:

.. code-block:: bash

   gunicorn my-flask-app:app --bind 0.0.0.0:5000

As a result, your application will be available at http://localhost:5000/ and pygeoapi will be available
at http://localhost:5000/my-pygeoapi


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

To integrate pygeoapi as part of another Starlette application you can use the factory function
defined in ``pygeoapi.starlette_app``, which returns an ASGI application which can be mounted onto
your own starlette app:


.. code-block:: python

   # my-custom-starlette-app.py
   from starlette.applications import Starlette
   from starlette.responses import HTMLResponse
   from starlette.routing import Route

   from pygeoapi.starlette_app import create_app


   async def homepage(request):
       # inside a starlette route, you can retrieve the pygeoapi API object
       # for this you need to get a hold of the relevant mount and extract it
       # from the mount's app.state.PYGEOAPI variable
       pygeoapi_mount = [m for m in request.app.routes if m.name == 'pygeoapi'][0]
       pygeoapi_ = pygeoapi_mount.app.state.PYGEOAPI
       return HTMLResponse(
           f'<h1>This is a uber fantastichen pygeoapi-enabled starlette app</h1>'
           f'<p>Oh, and the pygeoapi server description is: '
           f'{pygeoapi_.config["metadata"]["identification"]["title"]["en"]}</p>'
       )


   pygeoapi_app = create_app('example-config.yml', 'example-openapi.yml')

   app = Starlette(
       debug=True,
       routes=[
           Route('/', homepage),
       ]
   )

   app.mount('/my-pygeoapi', pygeoapi_app, name='pygeoapi')


The application above can be run, for example, with:

.. code-block:: bash

   gunicorn my-starlette-app:app --worker-class pygeoapi.starlette_app.PygeoapiUvicornWorker --bind 0.0.0.0:5000

As a result, your application will be available at http://localhost:5000/ and pygeoapi will be available
at http://localhost:5000/my-pygeoapi

.. note::
   In the above code snippet we provided the ``--worker-class pygeoapi.starlette_app.PygeoapiUvicornWorker`` flag.
   This custom pygeoapi worker exists specifically to overcome a bug in gunicorn whereby reloading does not work
   when used with uvicorn - read more about it here:

   https://github.com/benoitc/gunicorn/issues/2339


Django
^^^^^^

`Django`_ is a Python web framework that encourages rapid development and clean, pragmatic design. 

Similarly to Flask and Starlette, Django can be used by pygeoapi to communicate with the core API.

.. code-block:: bash

   HTTP request <--> Django (pygeoapi/django_app.py) <--> pygeoapi API (pygeoapi/api.py)

To use Django as a web server it is necessary to install its dependencies running the following command:

.. code-block:: bash

   pip3 install -r requirements-django.txt

After Django dependencies are installed, pygeoapi can be run as follows:

.. code-block:: bash

    pygeoapi serve --django

As a result, your Django application will be available at http://localhost:5000/.


To integrate pygeoapi as part of another Django project in a pluggable it is necessary to add the pygeoapi urls to the 
main Django application urls:

.. code-block:: python

   from django.contrib import admin
   from django.urls import path, include

   from pygeoapi.django_ import urls as pygeoapi_urls

   urlpatterns = [
      path('admin/', admin.site.urls),
      path('sample-project/', include(pygeoapi_urls)),
   ]

Additionally, the django settings module is expected to contain the following:

.. code-block:: python

   PYGEOAPI_CONFIG = None  # replace with the contents of pygeoapi configuration file
   PYGEOAPI_OPENAPI = None  # replace with the contents of pygeoapi openapi document
   API_RULES = None  # replace with an instance of pygeoapi.models.config.APIRules
   APPEND_SLASH = None


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

Running pygeoapi in production can also be achieved by using ``pygeoapi serve``, just remember to not include
the ``--debug`` flag.

.. seealso::
   :ref:`running-with-docker` for container-based production installations.

Apache and mod_wsgi
^^^^^^^^^^^^^^^^^^^

Deploying pygeoapi via `mod_wsgi`_ provides a simple approach to enabling within Apache.

To deploy with mod_wsgi, your Apache instance must have mod_wsgi enabled within Apache.  At this point,
set up the following Python WSGI script:

.. code-block:: python

   from pygeoapi.flask_app import create_app
   application = create_app(
       pygeoapi_config_path='/path/to/my-pygeoapi-config.yml'
       pygeoapi_openapi_path='/path/to/my-pygeoapi-openapi.yml'
   )

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

`Gunicorn`_ (for UNIX) is one of several Python WSGI HTTP servers that can be used for production environments,
and ``pygeoapi serve`` already make use of it.

.. code-block:: bash

   HTTP request --> WSGI or ASGI server (gunicorn) <--> Flask or Starlette (pygeoapi/flask_app.py or pygeoapi/starlette_app.py) <--> pygeoapi API

.. note::
   For a complete list of WSGI server implementations, see the `WSGI server list`_.


Gunicorn and Flask
^^^^^^^^^^^^^^^^^^

Gunicorn and Flask is simple to run. As mentioned above, ``pygeoapi serve`` also accepts gunicorn parameters. For
example, for running with 4 workers:

.. code-block:: bash

   pygeoapi serve -- --workers=4

.. note::
   For extra gunicorn configuration parameters please consult the `Gunicorn settings`_.


Gunicorn and Starlette
^^^^^^^^^^^^^^^^^^^^^^

Running Gunicorn with Starlette requires the `Uvicorn`_ library, which provides async capabilities along with Gunicorn.
Uvicorn includes a Gunicorn worker class allowing you to run ASGI applications, with all of Uvicorn's performance
benefits, while also giving you Gunicorn's fully-featured process management.

It is simple to run using the following command:

.. code-block:: bash

   pygeoapi serve --starlette -- --workers=4


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
