.. _configuration:

Configuration
=============

Once you have installed pygeoapi, it's time to setup a configuration.  pygeoapi's runtime configuration is defined
in the `YAML`_ format which is then referenced via the ``PYGEOAPI_CONFIG`` environment variable.  You can name the
file whatever you wish; typical filenames end with ``.yml``.

.. note::
   A sample configuration can always be found in the pygeoapi `GitHub <https://github.com/geopython/pygeoapi/blob/master/pygeoapi-config.yml>`_
   repository.

pygeoapi configuration contains the following core sections:

- ``server``: server-wide settings
- ``logging``: logging configuration
- ``metadata``: server-wide metadata (contact, licensing, etc.)
- ``resources``: dataset collections, processes and stac-collections offered by the server

.. note::
   `Standard YAML mechanisms <https://en.wikipedia.org/wiki/YAML#Advanced_components>`_ can be used (anchors, references, etc.) for reuse and compactness.

Configuration directives and reference are described below via annotated examples.

Reference
---------

``server``
^^^^^^^^^^

The ``server`` section provides directives on binding and high level tuning.

.. code-block:: yaml

  server:
    bind:
        host: 0.0.0.0  # listening address for incoming connections
        port: 5000  # listening port for incoming connections
    url: http://localhost:5000/  # url of server
    mimetype: application/json; charset=UTF-8  # default MIME type
    encoding: utf-8  # default server encoding
    language: en-US  # default server language
    cors: true  # boolean on whether server should support CORS
    pretty_print: true  # whether JSON responses should be pretty-printed
    limit: 10  # server limit on number of items to return
    map:  # leaflet map setup for HTML pages
        url: https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png
        attribution: '<a href="https://wikimediafoundation.org/wiki/Maps_Terms_of_Use">Wikimedia maps</a> | Map data &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
    ogc_schemas_location: /opt/schemas.opengis.net  # local copy of http://schemas.opengis.net


``logging``
^^^^^^^^^^^

The ``logging`` section provides directives for logging messages which are useful for debugging.

.. code-block:: yaml

  logging:
      level: ERROR  # the logging level (see https://docs.python.org/3/library/logging.html#logging-levels)
      logfile: /path/to/pygeoapi.log  # the full file path to the logfile

.. note::
   If ``level`` is defined and ``logfile`` is undefined, logging messages are output to the server's ``stdout``.


``metadata``
^^^^^^^^^^^^

The ``metadata`` section provides settings for overall service metadata and description.

.. code-block:: yaml

  metadata:
      identification:
          title: pygeoapi default instance  # the title of the service
          description: pygeoapi provides an API to geospatial data  # some descriptive text about the service
          keywords:  # list of keywords about the service
              - geospatial
              - data
              - api
          keywords_type: theme  # keyword type as per the ISO 19115 MD_KeywordTypeCode codelist). Accepted values are discipline, temporal, place, theme, stratum
          terms_of_service: https://creativecommons.org/licenses/by/4.0/  # terms of service
          url: http://example.org  # informative URL about the service
      license:  # licensing details
          name: CC-BY 4.0 license
          url: https://creativecommons.org/licenses/by/4.0/
      provider:  # service provider details
          name: Organization Name
          url: https://pygeoapi.io
      contact:  # service contact details
          name: Lastname, Firstname
          position: Position Title
          address: Mailing Address
          city: City
          stateorprovince: Administrative Area
          postalcode: Zip or Postal Code
          country: Country
          phone: +xx-xxx-xxx-xxxx
          fax: +xx-xxx-xxx-xxxx
          email: you@example.org
          url: Contact URL
          hours: Mo-Fr 08:00-17:00
          instructions: During hours of service. Off on weekends.
          role: pointOfContact

``resources``
^^^^^^^^^^^^^

The ``resources`` section lists 1 or more dataset collections to be published by the server.

The ``resource.type`` property is required.  Allowed types are:

- ``collection``
- ``process``
- ``stac-collection``

The ``providers`` block is a list of 1..n providers with which to operate the data on.  Each 
provider requires a ``type`` property.  Allowed types are:

- ``feature``

A collection's default provider can be qualified with ``default: true`` in the provider
configuration.  If ``default`` is not included, the first provider is assumed to be the
default.

.. code-block:: yaml

  resources:
      obs:
          type: collection  # REQUIRED (collection, process, or stac-collection)
          title: Observations  # title of dataset
          description: My cool observations  # abstract of dataset
          keywords:  # list of related keywords
              - observations
              - monitoring
          context:  # linked data configuration (see Linked Data section)
              - datetime: https://schema.org/DateTime
              - vocab: https://example.com/vocab#
                stn_id: "vocab:stn_id"
                value: "vocab:value"
          links:  # list of 1..n related links
              - type: text/csv  # MIME type
                rel: canonical  # link relations per https://www.iana.org/assignments/link-relations/link-relations.xhtml
                title: data  # title
                href: https://github.com/mapserver/mapserver/blob/branch-7-0/msautotest/wxs/data/obs.csv  # URL
                hreflang: en-US  # language
          extents:  # spatial and temporal extents
              spatial:  # required
                  bbox: [-180,-90,180,90]  # list of minx, miny, maxx, maxy
                  crs: http://www.opengis.net/def/crs/OGC/1.3/CRS84  # CRS
              temporal:  # optional
                  begin: 2000-10-30T18:24:39Z  # start datetime in RFC3339
                  end: 2007-10-30T08:57:29Z  # end datetime in RFC3339
          providers:  # list of 1..n required connections information
              # provider name
              # see pygeoapi.plugin for supported providers
              # for custom built plugins, use the import path (e.g. mypackage.provider.MyProvider)
              # see Plugins section for more information
              - type: feature # underlying data geospatial type: (allowed values are: feature)
                default: true  # optional: if not specified, the first provider definition is considered the default
                name: CSV
                data: tests/data/obs.csv  # required: the data filesystem path or URL, depending on plugin setup
                id_field: id  # required for vector data, the field corresponding to the ID
                time_field: datetimestamp  # optional field corresponding to the temporal propert of the dataset
                properties:  # optional: only return the following properties, in order
                    - stn_id
                    - value

      hello-world:  # name of process
          type: collection  # REQUIRED (collection, process, or stac-collection)
          processor:
              name: HelloWorld  # Python path of process defition


.. seealso::
   `Linked Data`_ for optionally configuring linked data datasets

.. seealso::
   :ref:`plugins` for more information on plugins


Using environment variables
---------------------------

pygeoapi configuration supports using system environment variables, which can be helpful
for deploying into `12 factor <https://12factor.net/>`_ environments for example.

Below is an example of how to integrate system environment variables in pygeoapi.

.. code-block:: yaml

   server:
       bind:
           host: ${MY_HOST}
           port: ${MY_PORT}


Linked Data
-----------

.. image:: https://json-ld.org/images/json-ld-logo-64.png
    :width: 64px
    :align: left
    :alt: JSON-LD support

pygeoapi supports structured metadata about a deployed instance, and is also capable of presenting data as
structured data. `JSON-LD`_ equivalents are available for each HTML page, and are embedded
as data blocks within the corresponding page for search engine optimisation (SEO).  Tools such as the
`Google Structured Data Testing Tool`_ can be used to check the structured representations.

The metadata for an instance is determined by the content of the `metadata`_ section of the configuration.
This metadata is included automatically, and is sufficient for inclusion in major indices of datasets, including the
`Google Dataset Search`_.

For collections, at the level of an item or items, by default the JSON-LD representation adds:

- The GeoJSON JSON-LD `vocabulary and context <https://geojson.org/geojson-ld/>`_ to the ``@context``.
- An ``@id`` for each item in a collection, that is the URL for that item (resolving to its HTML representation
  in pygeoapi)

.. note::
   While this is enough to provide valid RDF (as GeoJSON-LD), it does not allow the *properties* of your items to be
   unambiguously interpretable.

pygeoapi currently allows for the extension of the ``@context`` to allow properties to be aliased to terms from
vocabularies.  This is done by adding a ``context`` section to the configuration of a ``dataset``.

The default pygeoapi configuration includes an example for the ``obs`` sample dataset:

.. code-block:: yaml

  context:
      - datetime: https://schema.org/DateTime
      - vocab: https://example.com/vocab#
        stn_id: "vocab:stn_id"
        value: "vocab:value"

This is a non-existent vocabulary included only to illustrate the expected data structure within the configuration.
In particular, the links for the ``stn_id`` and ``value`` properties do not resolve. We can extend this example to
one with terms defined by schema.org:

.. code-block:: yaml

  context:
      - schema: https://schema.org/
        stn_id: schema:identifer
        datetime:
            "@id": schema:observationDate
            "@type": schema:DateTime
        value:
            "@id": schema:value
            "@type": schema:Number

Now this has been elaborated, the benefit of a structured data representation becomes clearer.  What was once an
unexplained property called ``datetime`` in the source CSV, it can now be `expanded <https://www.w3.org/TR/json-ld-api/#expansion-algorithms>`_
to `<https://schema.org/observationDate>`_, thereby eliminating ambiguity and enhancing interoperability.  Its type is
also expressed as `<https://schema.org/DateTime>`_.

This example demonstrates how to use this feature with a CSV data provider, using included sample data. The
implementation of JSON-LD structured data is available for any data provider but is currently limited to defining a
``@context``.  Relationships between items can be expressed but is dependent on such relationships being expressed
by the dataset provider, not pygeoapi.


Data Transactions
-----------------
pygeoapi in compliance with `OGC API - Features - Part 4: Simple Transactions <http://docs.opengeospatial.org/DRAFTS/20-002.html>`_ supports create, update, replace and delete operations. A collection resource supporting data transactions will have POST, PATCH, PUT and DELETE HTTP verbs in its RESTful API.

Data transaction support is optional and can be enabled for a collection resource by adding ``transactions: true`` to ``extensions`` under the resource in the pygeoapi config file. If transactions parameter is not set it will be considered as ``transactions: false``.

The default pygeoapi configuration includes an example for the ``obs`` sample dataset:

.. code-block:: yaml

  resources:
      obs:
          type: collection
          extensions:
              transactions: true


Summary
-------

At this point, you have the configuration ready to administer the server.


.. _`YAML`: https://en.wikipedia.org/wiki/YAML
.. _`JSON-LD`: https://json-ld.org
.. _`Google Structured Data Testing Tool`: https://search.google.com/structured-data/testing-tool#url=https%3A%2F%2Fdemo.pygeoapi.io%2Fmaster
.. _`Google Dataset Search`: https://developers.google.com/search/docs/data-types/dataset
