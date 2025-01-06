.. _running-with-docker:

Docker
======

pygeoapi provides an official `Docker`_ image which is made available on both the `geopython Docker Hub`_ and our `GitHub Container Registry`_.  Additional
Docker examples can be found in the `pygeoapi GitHub repository`_, each with sample configurations, test data,
deployment scenarios and provider backends.

The `pygeoapi demo server`_ runs various services from Docker images which also serve as `useful examples`_.

.. note::
   Both Docker and `Docker Compose`_ are required on your system to run pygeoapi images.

The basics
----------

The official pygeoapi Docker image will start a pygeoapi Docker container using Gunicorn on internal port 80.

Either ``IMAGE`` can be called with the ``docker`` command, ``geopython/pygeoapi`` from DockerHub or ``ghcr.io/geopython/pygeoapi`` from the GitHub Container Registry. Examples below use ``geopython/pygeoapi``. 

To run with the default built-in configuration and data:

.. code-block:: bash

   docker run -p 5000:80 -it geopython/pygeoapi run
   # or simply
   docker run -p 5000:80 -it geopython/pygeoapi

...then browse to http://localhost:5000

You can also run all unit tests to verify:

.. code-block:: bash

   docker run -it geopython/pygeoapi test


Overriding the default configuration
------------------------------------

Normally you would override the ``default.config.yml`` with your own ``pygeoapi`` configuration.
This can be done via Docker Volume Mapping.

For example, if your config is in ``my.config.yml``:

.. code-block:: bash

   docker run -p 5000:80 -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi


For a cleaner approach, You can use ``docker-compose`` as per below:

.. code-block:: yaml

   version: "3"
   services:
     pygeoapi:
       image: geopython/pygeoapi:latest
       volumes:
         - ./my.config.yml:/pygeoapi/local.config.yml
       ports:
         - "5000:80"

Or you can create a ``Dockerfile`` extending the base image and **copy** in your configuration:

.. code-block:: dockerfile

   FROM geopython/pygeoapi:latest
   COPY ./my.config.yml /pygeoapi/local.config.yml

A corresponding example can be found in https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi_master

Environment Variables for Configuration
---------------------------------------

The base Docker image supports two additional environment variables for configuring the `pygeoapi` server behavior:

1. **`PYGEOAPI_SERVER_URL`**:  
   This variable sets the `pygeoapi` server URL in the configuration. It is useful for dynamically configuring the server URL during container deployment. For example:

   .. code-block:: bash

      docker run -p 2018:80 -e PYGEOAPI_SERVER_URL='http://localhost:2018' -it geopython/pygeoapi

   This ensures the service URLs in the configuration file are automatically updated to reflect the specified URL.

2. **`PYGEOAPI_SERVER_ADMIN`**:  
   This boolean environment variable enables or disables the `pygeoapi` Admin API. By default, the Admin API is disabled. To enable it:

   .. code-block:: bash

      docker run -p 5000:80 -e PYGEOAPI_SERVER_ADMIN=true -it geopython/pygeoapi

   This does not enable hot reloading of the `pygeoapi` configuration. To learn more about the Admin API see :ref:`admin-api`.


Deploying on a sub-path
-----------------------

By default the ``pygeoapi`` Docker image will run from the ``root`` path (``/``).  If you need to run from a
sub-path and have all internal URLs properly configured, you can set the ``SCRIPT_NAME`` environment variable.

For example to run with ``my.config.yml`` on ``http://localhost:5000/mypygeoapi``:

.. code-block:: bash

   docker run -p 5000:80 -e SCRIPT_NAME='/mypygeoapi' -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi


...then browse to **http://localhost:5000/mypygeoapi**

Below is a corresponding ``docker-compose`` approach:

.. code-block:: yaml

   version: "3"
   services:
     pygeoapi:
       image: geopython/pygeoapi:latest
       volumes:
         - ./my.config.yml:/pygeoapi/local.config.yml
       ports:
         - "5000:80"
       environment:
        - SCRIPT_NAME=/pygeoapi

A corresponding example can be found in https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi_master

Summary
-------

Docker is an easy and reproducible approach to deploying systems.

.. note::
   Additional approaches are welcome and encouraged; see :ref:`contributing` for more information on
   how to contribute to and improve the documentation


.. _`Docker`: https://www.docker.com
.. _`geopython Docker Hub`: https://hub.docker.com/r/geopython/pygeoapi
.. _`GitHub Container Registry`: https://github.com/geopython/pygeoapi/pkgs/container/pygeoapi
.. _`pygeoapi GitHub repository`: https://github.com/geopython/pygeoapi
.. _`pygeoapi demo server`: https://demo.pygeoapi.io
.. _`useful examples`: https://github.com/geopython/demo.pygeoapi.io/tree/master/services
.. _`Docker Compose`: https://docs.docker.com/compose/
