.. _admin-api:

Admin API
=========

When the Admin API is enabled, :ref:`transactions` can be made on pygeoapi's configured resources.
This allows for on the fly addition and modification of the data served by pygeoapi.
The API is enabled with the server configuration:

.. code-block:: yaml

    server:
        admin: true # boolean on whether to enable admin api.

For pygeoapi to hot reload the configuration as changes are made, the pygeoapi configuration file must be included as
demonstrated for a gunicorn deployment of pygeoapi via flask:

.. code-block:: bash

    gunicorn \
        --workers ${WSGI_WORKERS} \
        --worker-class=${WSGI_WORKER_CLASS} \
        --timeout ${WSGI_WORKER_TIMEOUT} \
        --name=${CONTAINER_NAME} \
        --bind ${CONTAINER_HOST}:${CONTAINER_PORT} \
        --reload \
        --reload-extra-file ${PYGEOAPI_CONFIG} \
        pygeoapi.flask_app:APP
