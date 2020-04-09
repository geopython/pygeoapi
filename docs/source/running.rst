.. _running:

Running
=======

Now we are ready to start up pygeoapi.


``pygeoapi serve``
------------------

The ``pygeoapi serve`` command starts up an instance using Flask as the default server.  pygeoapi
can be served via Flask `WSGI`_ or Starlette `ASGI`_.

Since pygeoapi is a Python API at its core, it can be served via numerous web server scenarios.

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

Gunicorn overview
^^^^^^^^^^^^^^^^^

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


.. _`WSGI`: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface
.. _`ASGI`: https://asgi.readthedocs.io
.. _`Gunicorn`: https://gunicorn.org
.. _`WSGI server list`: https://wsgi.readthedocs.io/en/latest/servers.html
.. _`Gunicorn settings`: http://docs.gunicorn.org/en/stable/settings.html
.. _`Uvicorn`: https://www.uvicorn.org
