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
- ``datasets``: dataset collections offered by server
- ``processes``: processes offered by server

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
    pretty_print: true  # whether JSON responses should be pretty printed
    limit: 10  # server limit on number of features to return
    map:  # leaflet map setup for HTML pages
        url: https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png
        attribution: '<a href="https://wikimediafoundation.org/wiki/Maps_Terms_of_Use">Wikimedia maps</a> | Map data &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
    ogc_schemas_location: /opt/schemas.opengis.net  # local copy of http://schemas.opengis.net


``logging``
^^^^^^^^^^^

The ``logging`` section provides directives for logging messages which are useful for debugging.

.. code-block:: yaml

  logging:
      level: ERROR # the logging level (see https://docs.python.org/3/library/logging.html#logging-levels)
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
          terms_of_service: null  # terms of service
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

``datasets``
^^^^^^^^^^^^

The ``datasets`` section lists 1 or more dataset collections to be published by the server.

.. code-block:: yaml

  datasets:
      obs:
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
          provider:  # required connection information
              # provider name
              # see pygeoapi.plugin for supported providers
              # for custom built plugins, use the import path (e.g. mypackage.provider.MyProvider
              # see Plugins section for more information
              name: CSV
              data: tests/data/obs.csv  # required: the data filesystem path or URL, depending on plugin setup
              id_field: id  # required for vector data, the field corresponding to the ID
              time_field: datetimestamp  # optional field corresponding to the temporal propert of the dataset

.. seealso::
   :ref:`linked-data` for configuring linked data datasets

.. seealso::
   :ref:`plugins` for more information on plugins


``processes``
^^^^^^^^^^^^^

.. code-block:: yaml

  processes:
      hello-world:  # name of process
          processor:
              name: HelloWorld  # Python path of process defition

.. note::
   See :ref:`processing-plugins` for more information on plugins


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


Summary
-------

At this point, you have the configuration ready to administer the server.


.. _`YAML`: https://en.wikipedia.org/wiki/YAML
