.. _pubsub:

Publish-Subscribe integration (Pub/Sub)
=======================================

pygeoapi supports Publish-Subscribe (Pub/Sub) integration by implementing
the `OGC API Publish-Subscribe Workflow - Part 1: Core`_ (draft) specification.

Pub/Sub integration can be enabled by defining a broker that pycsw can use to
publish notifications on given topics using CloudEvents (as per the specification).

When enabled, core functionality of Pub/Sub includes:

- providing an AsyncAPI document (JSON and HTML)
- providing the following links on the OGC API landing page:

  - the broker link (``rel=hub`` link relation)
  - the AsyncAPI JSON link (``rel=service-desc`` link relation and ``type=application/asyncapi+json`` media type)
  - the AsyncAPI HTML link (``rel=service-doc`` link relation and ``type=text/html`` media type)

- sending a notification message on the following events:

  - feature or record transactions (create, replace, update, delete)
  - process executions/job creation

AsyncAPI
--------

`AsyncAPI`_ is the event-driven equivalent to :ref:`openapi`

The official AsyncAPI specification can be found on the `AsyncAPI`_ website.  pygeoapi supports AsyncAPI version 3.0.0.

AsyncAPI is an optional capability in pygeoapi.  To enable AsyncAPI, the following steps are required:

- defining a ``pubsub`` section in configuration (see :ref:`configuration` and :ref:`brokers` for more information)
- generating an AsyncAPI document
- setting the ``PYGEOAPI_ASYNCAPI`` environment variable

Creating the AsyncAPI document
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The AsyncAPI document is a YAML or JSON configuration which is generated from the pygeoapi configuration, and describes the server information, channels and the message payloads structures.

To generate the AsyncAPI document, run the following:

.. code-block:: bash

   pygeoapi asyncapi generate /path/to/my-pygeoapi-config.yml

This will dump the AsyncAPI document as YAML to your system's ``stdout``.  To save to a file on disk, run:

.. code-block:: bash

   pygeoapi asyncapi generate /path/to/my-pygeoapi-config.yml --output-file /path/to/my-pygeoapi-asyncapi.yml

To generate the AsyncAPI document as JSON, run:

.. code-block:: bash

   pygeoapi asyncapi generate /path/to/my-pygeoapi-config.yml --format json --output-file /path/to/my-pygeoapi-asyncapi.json

.. note::
   Generate as YAML or JSON?  If your AsyncAPI YAML definition is slow to render as JSON,
   saving as JSON to disk will help with performance at run-time.

.. note::
   The AsyncAPI document provides detailed information on query parameters, and dataset
   property names and their data types.  Whenever you make changes to your pygeoapi configuration,
   always refresh the accompanying AsyncAPI document.

Validating the AsyncAPI document
--------------------------------

To ensure your AsyncAPI document is valid, pygeoapi provides a validation
utility that can be run as follows:

.. code-block:: bash

   pygeoapi asyncapi validate /path/to/my-pygeoapi-asyncapi.yml

.. _brokers:

Brokers
-------

The following protocols are supported:

.. note::

   Pub/Sub client dependencies will vary based on the selected broker.  ``requirements-pubsub.txt`` contains all requirements for supported brokers, as a reference point.


MQTT
^^^^

Example directive:

.. code-block:: yaml

   pubsub:
       name: MQTT
       broker:
           url: mqtt://localhost:1883
           channel: messages/a/data  # optional
           hidden: false # default

Kafka
^^^^^

Example directive:

.. code-block:: yaml

   pubsub:
       name: Kafka
       broker:
           url: tcp://localhost:9092
           channel: messages-a-data
           # if using authentication:
           # sasl_mechanism: PLAIN  # default PLAIN
           # sasl_security_protocol: SASL_PLAINTEXT  # default SASL_PLAINTEXT
           hidden: true  # default false

HTTP
^^^^

Example directive:

.. code-block:: yaml

   pubsub:
       name: HTTP
       broker:
           url: https://ntfy.sh
           channel: messages-a-data  # optional
           hidden: true  # default false

Additional information
----------------------

.. note::

   For any Pub/Sub endpoints requiring authentication, encode the ``url`` value as follows:

   * ``mqtt://username:password@localhost:1883``
   * ``https://username:password@localhost``
   * ``tcp://username:password@localhost:9092``

   As with any section of the pygeoapi configuration, environment variables may be used as needed, for example
   to set username/password information in a URL.  If ``pubsub.broker.url`` contains authentication, and
   ``pubsub.broker.hidden`` is ``false``, the authentication information will be stripped from the URL
   before displaying it on the landing page.

.. note::

   If a ``channel`` is defined, it is used as a prefix to the relevant OGC API endpoint used.

   If a ``channel`` is not defined, only the relevant OGC API endpoint is used.


.. _`OGC API Publish-Subscribe Workflow - Part 1: Core`: https://docs.ogc.org/DRAFTS/25-030.html
.. _`AsyncAPI`: https://www.asyncapi.com
