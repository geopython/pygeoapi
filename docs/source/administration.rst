.. _administration:

Administration
==============

Now that you have pygeoapi installed and a basic configuration setup, it's time to complete
the administrative steps required before starting up the server.  The remaining steps are:

- create OpenAPI document
- set system environment variables

Creating the OpenAPI document
-----------------------------

The OpenAPI document ia a YAML configuration which is generated from the pygeoapi configuration,
and describes the server information, endpoints, and parameters.

To generate the OpenAPI document, run the following:

.. code-block:: bash

   pygeoapi generate-openapi-document -c /path/to/my-pygeoapi-config.yml

This will dump the OpenAPI document as YAML to your system's ``stdout``.  To save to file, run:

.. code-block:: bash

   pygeoapi generate-openapi-document -c /path/to/my-pygeoapi-config.yml > /path/to/my-pygeoapi-openapi.yml


.. seealso::
   :ref:`openapi` for more information on pygeoapi's OpenAPI support


OpenAPI document management
---------------------------

Note that the OpenAPI document provides detailed information on query parameters, and dataset
property names and their data types.  Whenever you make changes to your pygeoapi configuration,
always refresh the accompanying OpenAPI document.

Verifying configuration files
-----------------------------

To ensure your YAML configurations are correctly formatted, you can use any YAML validator, or try
the Python one-liner per below:

.. code-block:: bash

   python -c 'import yaml, sys; yaml.safe_load(sys.stdin)' < /path/to/my-pygeoapi-config.yml
   python -c 'import yaml, sys; yaml.safe_load(sys.stdin)' < /path/to/my-pygeoapi-openapi.yml


Setting system environment variables
------------------------------------

Now, let's set our system environment variables.

In UNIX:

.. code-block:: bash

    export PYGEOAPI_CONFIG=/path/to/my-pygeoapi-config.yml
    export PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.yml

In Windows:

.. code-block:: bat

    set PYGEOAPI_CONFIG=/path/to/my-pygeoapi-config.yml
    set PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.yml

Summary
-------

At this point you are ready to run the server.  Let's go!
