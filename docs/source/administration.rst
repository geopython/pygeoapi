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


.. note::

   See :ref:`openapi` for more inforamtion on pygeoapi's OpenAPI support.


Verifying configuration files
-----------------------------

To ensure your YAML configurations are correctly formatted, you can use any YAML validator, or try
the Python one-liner per below:

.. code-block:: bash

   python -c 'import yaml, sys; yaml.safe_load(sys.stdin)' < /path/to/my-pygeoapi-config.yml
   python -c 'import yaml, sys; yaml.safe_load(sys.stdin)' < /path/to/my-pygeoapi-openapi.yml


Setting system environment variables
------------------------------------

Now let's set our system environment variables.

In UNIX:

.. code-block:: bash

    export PYGEOAPI_CONFIG=/path/to/my-pygeoapi-config.yml
    export PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.yml

In Windows:

.. code-block:: bat

    set PYGEOAPI_CONFIG=/path/to/my-pygeoapi-config.yml
    set PYGEOAPI_OPENAPI=/path/to/my-pygeoapi-openapi.yml
