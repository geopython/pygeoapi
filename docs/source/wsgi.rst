.. _wsgi:

WSGI
====

 Web Server Gateway Interface (WSGI) is  standard for forwarding request to web applications written on Python language. pygeoapi it self
 doesn't implement WSGI since it is an API, 
 therefore it is required a webframework to access HTTP requests and pass the information to pygeoapi
 
.. code-block:: console
 
   HTTP request --> Flask (flask_app.py) --> pygeopai API   

   
the pygeoapi package integrates `Flask <https://flask.palletsprojects.com/en/1.1.x/>`_ as webframework for defining the API routes/end points and WSGI support.

The flask WSGI server can be easily run as a pygeoapi command with the option `--flask`:

.. code-block:: console

   pygeoapi serve --flask

Running a native Flask server is not advisable, the prefered option is as follows:

.. code-block:: console
 
   HTTP request --> WSGI server (gunicorn) --> Flask (flask_app.py) --> pygeoapi API

By having a specific WSGI server, the HTTPS are efficiently processed into threads/processes. The current docker pygeoapi 
implement such strategy (see section: :ref:`docker`), it is prefered to implement pygeopai using docker solutions than running host native WSGI servers.


Running gunicorn
----------------

Gunicorn is one of several WSGI supporting server on python (list of server supporting WSGI: `here <https://wsgi.readthedocs.io/en/latest/servers.html>`_). This server
is simple to run from the command, e.g:

.. code-block:: console
   
   gunicorn pygeoapi.flask_app:APP

For extra configuration parameters like port binding, workers please consult the gunicorn `settings <http://docs.gunicorn.org/en/stable/settings.html>`_




 