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

The following message queuing protocols are supported:

MQTT
----

Example directive:

.. code-block:: yaml

   pubsub:
       name: MQTT
       broker:
           url: mqtt://localhost:1883
           channel: messages/a/data  # optional
           hidden: false # default

HTTP
----

Example directive:

.. code-block:: yaml

   pubsub:
       name: HTTP
       broker:
           url: https://ntfy.sh
           channel: messages-a-data  # optional
           hidden: true  # default false

.. note::

   For any Pub/Sub endpoints requiring authentication, encode the ``url`` value as follows:

   * ``mqtt://username:password@localhost:1883``
   * ``https://username:password@localhost``

   As with any section of the pygeoapi configuration, environment variables may be used as needed, for example
   to set username/password information in a URL.  If ``pubsub.broker.url`` contains authentication, and
   ``pubsub.broker.hidden`` is ``false``, the authentication information will be stripped from the URL
   before displaying it on the landing page.

.. note::

   If a ``channel`` is defined, it is used as a prefix to the relevant OGC API endpoint used.

   If a ``channel`` is not defined, only the relevant OGC API endpoint is used.

.. _`OGC API Publish-Subscribe Workflow - Part 1: Core`: https://docs.ogc.org/DRAFTS/25-030.html
