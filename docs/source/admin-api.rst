.. _admin-api:

Admin API
=========

pygeoapi provides the ability to manage configuration through an API.

When enabled, :ref:`transactions` can be made on pygeoapi's configured resources.  This allows for API based modification of the pygeoapi configuration.

The API is enabled with the following server configuration:

.. code-block:: yaml

    server:
        admin: true # boolean on whether to enable Admin API.

Access control
--------------

It should be made clear that authentication and authorization is beyond the responsibility of pygeoapi.  This means that
if a pygeoapi user enables the Admin API, they must provide access control explicity via another service.

pygeoapi hot reloading in gunicorn
----------------------------------

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
