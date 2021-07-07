.. _administration:

Administration
==============

Now that you have pygeoapi installed and a basic configuration setup, it's time to complete
the administrative steps required before starting up the server.  The remaining steps are:

- create OpenAPI document
- validate OpenAPI document
- set system environment variables

Creating the OpenAPI document
-----------------------------

The OpenAPI document is a YAML configuration which is generated from the pygeoapi configuration,
and describes the server information, endpoints, and parameters.

To generate the OpenAPI document, run the following:

.. code-block:: bash

   pygeoapi openapi generate /path/to/my-pygeoapi-config.yml

This will dump the OpenAPI document as YAML to your system's ``stdout``.  To save to a file on disk, run:

.. code-block:: bash

   pygeoapi openapi generate /path/to/my-pygeoapi-config.yml > /path/to/my-pygeoapi-openapi.yml

To generate the OpenAPI document as JSON, run:

.. code-block:: bash

   pygeoapi openapi generate /path/to/my-pygeoapi-config.yml -f json > /path/to/my-pygeoapi-openapi.json

.. note::
   Generate as YAML or JSON?  If your OpenAPI YAML definition is slow to render as JSON,
   saving as JSON to disk will help with performance at run-time.

.. note::
   The OpenAPI document provides detailed information on query parameters, and dataset
   property names and their data types.  Whenever you make changes to your pygeoapi configuration,
   always refresh the accompanying OpenAPI document.


.. seealso::
   :ref:`openapi` for more information on pygeoapi's OpenAPI support


Validating the OpenAPI document
-------------------------------

To ensure your OpenAPI document is valid, pygeoapi provides a validation
utility that can be run as follows:

.. code-block:: bash

   pygeoapi openapi validate /path/to/my-pygeoapi-openapi.yml


Setting system environment variables
------------------------------------

Now, let's set our system environment variables.

In UNIX:

.. code-block:: bash

    export PYGEOAPI_CONFIG=/path/to/my-pygeoapi-config.yml
    export PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.yml
    # or if OpenAPI JSON
    export PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.json

In Windows:

.. code-block:: bat

    set PYGEOAPI_CONFIG=/path/to/my-pygeoapi-config.yml
    set PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.yml
    # or if OpenAPI JSON
    set PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.json


Summary
-------

At this point you are ready to run the server.  Let's go!
