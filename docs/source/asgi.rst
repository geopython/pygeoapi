.. _asgi:

ASGI
====

Asynchronous Server Gateway Interface (ASGI) is standard interface between async-capable web servers, frameworks, and applications written on Python language. pygeoapi itself
doesn't implement ASGI since it is an API, therefore it is required a webframework to access HTTP requests and pass the information to pygeoapi

.. code-block:: console

    HTTP request --> Starlette (starlette_app.py) --> pygeoapi API


the pygeoapi package integrates `starlette_app <https://www.starlette.io/>`_ as webframework for defining the API routes/end points and WSGI support.

The starlette ASGI server can be easily run as a pygeoapi command with the option `--starlette`:

.. code-block:: console

    pygeoapi serve --starlette

Running a Uvicorn server is not advisable, the preferred option is as follows:

.. code-block:: console

    HTTP request --> ASGI server (gunicorn) --> Starlette (starlette_app.py) --> pygeoapi API

By having a specific ASGI server, the HTTPS are efficiently processed into threads/processes. The current docker pygeoapi
implement such strategy (see section: :ref:`docker`), it is prefered to implement pygeopai using docker solutions than running host native ASGI servers.


Running gunicorn
----------------

Uvicorn includes a Gunicorn worker class allowing you to run ASGI applications, with all of Uvicorn's performance benefits, while also giving you Gunicorn's fully-featured process management. This server
is simple to run from the command, e.g:

.. code-block:: console

    gunicorn pygeoapi.starlette_app:app -w 4 -k uvicorn.workers.UvicornWorker

For extra configuration parameters like port binding, workers please consult the gunicorn `settings <http://docs.gunicorn.org/en/stable/settings.html>`_
