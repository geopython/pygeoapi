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

The full configuration schema with descriptions of all available properties can be found `here <https://github.com/geopython/pygeoapi/blob/master/pygeoapi/schemas/config/pygeoapi-config-0.x.yml>`_.

.. note::
   `Standard YAML mechanisms <https://en.wikipedia.org/wiki/YAML#Advanced_components>`_ can be used (anchors, references, etc.) for reuse and compactness.

Configuration directives and reference are described below via annotated examples.

Reference
---------

``server``
^^^^^^^^^^

The ``server`` section provides directives on binding and high level tuning.

For more information related to API design rules (the ``api_rules`` property in the example below) see :ref:`API Design Rules`.

.. code-block:: yaml

  server:
    bind:
        host: 0.0.0.0  # listening address for incoming connections
        port: 5000  # listening port for incoming connections
    url: http://localhost:5000/  # url of server
    mimetype: application/json; charset=UTF-8  # default MIME type
    encoding: utf-8  # default server encoding
    language: en-US  # default server language
    locale_dir: /path/to/translations
    gzip: false # default server config to gzip/compress responses to requests with gzip in the Accept-Encoding header
    cors: true  # boolean on whether server should support CORS
    pretty_print: true  # whether JSON responses should be pretty-printed
    limit: 10  # server limit on number of items to return

    templates: # optional configuration to specify a different set of templates for HTML pages. Recommend using absolute paths. Omit this to use the default provided templates
      path: /path/to/jinja2/templates/folder # path to templates folder containing the Jinja2 template HTML files
      static: /path/to/static/folder # path to static folder containing css, js, images and other static files referenced by the template

    map:  # leaflet map setup for HTML pages
        url: https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png
        attribution: '<a href="https://wikimediafoundation.org/wiki/Maps_Terms_of_Use">Wikimedia maps</a> | Map data &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
    ogc_schemas_location: /opt/schemas.opengis.net  # local copy of https://schemas.opengis.net

    manager:  # optional OGC API - Processes asynchronous job management
        name: TinyDB  # plugin name (see pygeoapi.plugin for supported process_manager's)
        connection: /tmp/pygeoapi-process-manager.db  # connection info to store jobs (e.g. filepath)
        output_dir: /tmp/  # temporary file area for storing job results (files)

    api_rules:  # optional API design rules to which pygeoapi should adhere
        api_version: 1.2.3  # omit to use pygeoapi's software version
        strict_slashes: true  # trailing slashes will not be allowed and result in a 404
        url_prefix: 'v{api_major}'  # adds a /v1 prefix to all URL paths
        version_header: X-API-Version  # add a response header of this name with the API version


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
          keywords_type: theme  # keyword type as per the ISO 19115 MD_KeywordTypeCode codelist. Accepted values are discipline, temporal, place, theme, stratum
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

The ``resources`` section lists 1 or more dataset collections to be published by the server.  The
key of the resource name is the advertised collection identifier.

The ``resource.type`` property is required.  Allowed types are:

- ``collection``
- ``process``
- ``stac-collection``

The ``providers`` block is a list of 1..n providers with which to operate the data on.  Each
provider requires a ``type`` property.  Allowed types are:

- ``feature``
- ``coverage``
- ``tile``

A collection's default provider can be qualified with ``default: true`` in the provider
configuration.  If ``default`` is not included, the *first* provider is assumed to be the
default.

.. code-block:: yaml

  resources:
      obs:
          type: collection  # REQUIRED (collection, process, or stac-collection)
          visibility: default  # OPTIONAL
          title: Observations  # title of dataset
          description: My cool observations  # abstract of dataset
          keywords:  # list of related keywords
              - observations
              - monitoring
          linked-data: # linked data configuration (see Linked Data section)
              item_template: tests/data/base.jsonld
              context:
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
              - type: feature # underlying data geospatial type: (allowed values are: feature, coverage, record, tile, edr)
                default: true  # optional: if not specified, the first provider definition is considered the default
                name: CSV
                data: tests/data/obs.csv  # required: the data filesystem path or URL, depending on plugin setup
                id_field: id  # required for vector data, the field corresponding to the ID
                uri_field: uri # optional field corresponding to the Uniform Resource Identifier (see Linked Data section)
                time_field: datetimestamp  # optional field corresponding to the temporal property of the dataset
                title_field: foo # optional field of which property to display as title/label on HTML pages
                properties:  # optional: only return the following properties, in order
                    - stn_id
                    - value
                # editable transactions: DO NOT ACTIVATE unless you have setup access control beyond pygeoapi
                editable: true  # optional: if backend is writable, default is false
                # coordinate reference systems (CRS) section is optional
                # default CRSs are http://www.opengis.net/def/crs/OGC/1.3/CRS84 (coordinates without height)
                # and http://www.opengis.net/def/crs/OGC/1.3/CRS84h (coordinates with ellipsoidal height)
                crs: # supported coordinate reference systems (CRS) for 'crs' and 'bbox-crs' query parameters
                    - http://www.opengis.net/def/crs/EPSG/0/28992
                    - http://www.opengis.net/def/crs/OGC/1.3/CRS84
                    - http://www.opengis.net/def/crs/EPSG/0/4326
                storage_crs: http://www.opengis.net/def/crs/OGC/1.3/CRS84 # optional CRS in which data is stored, default: as 'crs' field
                storage_crs_coordinate_epoch: : 2017.23 # optional, if storage_crs is a dynamic coordinate reference system
                format:  # optional default format
                    name: GeoJSON  # required: format name
                    mimetype: application/json  # required: format mimetype
                options:  # optional options to pass to provider (i.e. GDAL creation)
                    option_name: option_value

      hello-world:  # name of process
          type: collection  # REQUIRED (collection, process, or stac-collection)
          processor:
              name: HelloWorld  # Python path of process definition


.. seealso::
   `Linked Data`_ for optionally configuring linked data datasets

.. seealso::
   :ref:`plugins` for more information on plugins

Adding links to collections
---------------------------

You can add any type of link to a resource of type `collection`.
pygeoapi does not enforce anything here, as long as the link has a `type`, `rel`, and `href` parameter.
The `type` parameter defines the MIME type (`Content-Type`) of the linked resource.
The `rel` parameter tell something about what kind of link it is. You could set this to `license` to
add a data license link, or to `describedBy` if you wish to add a schema definition for example.

It's also possible to add (bulk) download links to a collection.
These links should have their `rel` parameter set to `enclosure` and must have a `length` parameter
that defines the content length (byte size) of the file.
If you know the content length and it never changes, you can set this and pygeoapi will return the enclosure link(s) as-is.

However, the downloadable resource may be subject to change (e.g. it may grow in size over time).
In that case, you can omit the `length` and pygeoapi will figure out the actual `Content-Length` header
by issuing a `HEAD` request on the given URL (`href` parameter).
Furthermore, if it notices that the defined `type` (MIME type) of the link does not match the actual
`Content-Type` in the response headers, it will automatically update the `type` accordingly.
Note that `type` is a mandatory link parameter though, so you must always set it.

So for example, you could define a download link like so:

.. code-block:: yaml

  links
    - type: application/octet-stream  # must have some MIME type
      rel: enclosure
      title: download link
      href: https://myserver.com/data/file.zip  # URL

And pygeoapi will turn that into:

.. code-block:: json

  {
    "links": {
      "type": "application/zip",
      "rel": "enclosure",
      "title": "download link",
      "href": "https://myserver.com/data/file.zip",
      "length": 46435
    }
  }

Note how the MIME type was updated to match the actual `Content-Type` and that the `length` was set
according to the `Content-Length` header.

.. note::

  If the `length` parameter is omitted and pygeoapi was not able to verify the `Content-Length` within 1 second
  and/or within 1 URL redirect, the enclosure link will **not** be included in the response.
  This means that if you want to be sure that the link is always included, you will have to set a `length`.


Publishing hidden resources
---------------------------

pygeoapi allows for publishing resources without advertising them explicitly
via its collections and OpenAPI endpoints.  The resource is available if the
client knows the name of the resource apriori.

To provide hidden resources, the resource must provide a ``visibility: hidden``
property.  For example, considering the following resource:

.. code-block:: yaml

   resources:
        foo:
            title: my hidden resource
            visibility: hidden

Examples:

.. code-block:: bash

   curl https://example.org/collections  # resource foo is not advertised
   curl https://example.org/openapi  # resource foo is not advertised
   curl https://example.org/collections/foo  # user can access resource normally


.. _API Design Rules:

API Design Rules
----------------

Some pygeoapi setups may wish to adhere to specific API design rules that apply at an organization.
The ``api_rules`` object in the ``server`` section of the configuration can be used for this purpose.

Note that the entire ``api_rules`` object is optional. No rules will be applied if the object is omitted.

The following properties can be set:

``api_version``
^^^^^^^^^^^^^^^

If specified, this property is a string that defines the semantic version number of the API.
Note that this number should reflect the state of the *API data model* (request and response object structure, API endpoints, etc.)
and does not necessarily correspond to the *software* version of pygeoapi. For example, the software could have been
completely rewritten (which changes the software version number), but the API data model might still be the same as before.

Unfortunately, pygeoapi currently does not offer a way to keep track of the API version.
This means that you need to set (and maintain) your own version here or leave it empty or unset.
In the latter case, the software version of pygeoapi will be used instead.

``strict_slashes``
^^^^^^^^^^^^^^^^^^

Some API rules state that trailing slashes at the end of a URL are not allowed if they point to a specific resource item.
In that case, you may wish to set this property to ``true``. Doing so will result in a ``404 Not Found`` if a user adds a ``/`` to the end of a URL.
If omitted or ``false`` (default), it does not matter whether the user omits or adds the ``/`` to the end of the URL.

``url_prefix``
^^^^^^^^^^^^^^

Set this property to include a prefix in the URL path (e.g. `https://base.com/<my_prefix>/endpoint`).
Note that you do not need to include slashes (either at the start or the end) here: they will be added automatically.

If you wish to include the API version number (depending on the `api_version`_ property) in the prefix, you can use the following variables:

- ``{api_version}``: full semantic version number
- ``{api_major}``: major version number
- ``{api_minor}``: minor version number
- ``{api_build}``: build number

For example, if the API version is *1.2.3*, then a URL prefix template of ``v{api_major}`` will result in *v1* as the actual prefix.

``version_header``
^^^^^^^^^^^^^^^^^^

Set this property to add a header to each pygeoapi response that includes the semantic API version (see `api_version`_).
If omitted, no header will be added. Common names for this header are ``API-Version`` or ``X-API-Version``.
Note that pygeoapi already adds a ``X-Powered-By`` header by default that includes the software version number.


Validating the configuration
----------------------------

To ensure your configuration is valid, pygeoapi provides a validation
utility that can be run as follows:

.. code-block:: bash

   pygeoapi config validate -c /path/to/my-pygeoapi-config.yml


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


Hierarchical collections
------------------------

Collections defined in the ``resources`` section are identified by the resource key.  The
key of the resource name is the advertised collection identifier.  For example, given the following:

.. code-block:: yaml

  resources:
    lakes:
      ...


The resulting collection will be made available at http://localhost:5000/collections/lakes

All collections are published by default to http://localhost:5000/collections.  To enable
hierarchical collections, provide the hierarchy in the resource key.  Given the following:

.. code-block:: yaml

  resources:
    naturalearth/lakes:
      ...

The resulting collection will then be made available at http://localhost:5000/collections/naturalearth/lakes

.. note::

  This functionality may change in the future given how hierarchical collection extension specifications
  evolve at OGC.

.. note::

  Collection grouping is not available.  This means that while URLs such as http://localhost:5000/collections/naturalearth/lakes
  function as expected, URLs such as  http://localhost:5000/collections/naturalearth will not provide
  aggregate collection listing or querying.  This functionality is also to be determined based on
  the evolution of hierarchical collection extension specifications at OGC.


Selective properties in feature and record providers
----------------------------------------------------

Providers defined in the ``providers`` section of a feature/record collection definition can support
selective properties to return only a subset of the schema attributes. This allows to
specialise the behavior of queryables and the GeoJSON's properties returned in the
payload.

For example, given the above example of the ``lakes`` collection a restriction on
the schema properties returned by its provider can be defined with the following:

.. code-block:: yaml

  resources:
    lakes:
      ...
      providers:
        - type: feature
          name: ...
          data:
            ...
          properties:
            - name

Examples:

.. code-block:: bash

  curl https://example.org/collections/lakes/queryables  # only the name definition is returned
  curl https://example.org/collections/lakes/items  # only the name attribute is returned in properties
  curl https://example.org/collections/lakes/items/{item_id}  # only the name attribute is returned in properties


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

For collections, at the level of item, the default JSON-LD representation adds:

- An ``@id`` for the item, which is the URL for that item. If uri_field is specified,
  it is used, otherwise the URL is to its HTML representation in pygeoapi.
- Separate GeoSPARQL/WKT and `schema.org/geo` versions of the geometry. `schema.org/geo`
  only supports point, line, and polygon geometries. Multipart lines are merged into a single line.
  The rest of the multipart geometries are transformed reduced and into a polygon via unary union
  or convex hull transform.
- ``@context`` for the GeoSPARQL and schema geometries.
- The unpacked properties block into the main body of the item.

For collections, at the level of items, the default JSON-LD representation adds:

- A schema.org itemList of the ``@id`` and ``@type`` of each feature in the collection.

The optional configuration options for collections, at the level of an item of items, are:

- If ``uri_field`` is specified, JSON-LD will be updated such that the ``@id`` has the value of ``uri_field`` for each item in a collection

.. note::
   While this is enough to provide valid RDF (as GeoJSON-LD), it does not allow the *properties* of your items to be
   unambiguously interpretable.

pygeoapi currently allows for the extension of the ``@context`` to allow properties to be aliased to terms from
vocabularies.  This is done by adding a ``context`` section to the configuration of a ``dataset``.

The default pygeoapi configuration includes an example for the ``obs`` sample dataset:

.. code-block:: yaml

  linked-data:
    context:
      - datetime: https://schema.org/DateTime
      - vocab: https://example.com/vocab#
        stn_id: "vocab:stn_id"
        value: "vocab:value"

This is a non-existent vocabulary included only to illustrate the expected data structure within the configuration.
In particular, the links for the ``stn_id`` and ``value`` properties do not resolve. We can extend this example to
one with terms defined by schema.org:

.. code-block:: yaml

  linked-data:
    context:
      - schema: https://schema.org/
        stn_id: schema:identifier
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

An example of a data provider that includes relationships between items is the SensorThings API provider.
SensorThings API, by default, has relationships between entities within its data model.
Setting the ``intralink`` field of the SensorThings provider to ``true`` sets pygeoapi
to represent the relationship between configured entities as intra-pygeoapi links or URIs.
This relationship can further be maintained in the JSON-LD structured data using the appropriate
``@context`` with the sosa/ssn ontology. For example:

.. code-block:: yaml

    Things:
      linked-data:
        context:
          - sosa: "http://www.w3.org/ns/sosa/"
            ssn: "http://www.w3.org/ns/ssn/"
            Datastreams: sosa:ObservationCollection

    Datastreams:
      linked-data:
        context:
          - sosa: "http://www.w3.org/ns/sosa/"
            ssn: "http://www.w3.org/ns/ssn/"
            Observations: sosa:hasMember
            Thing: sosa:hasFeatureOfInterest

    Observations:
      linked-data:
        context:
          - sosa: "http://www.w3.org/ns/sosa/"
            ssn: "http://www.w3.org/ns/ssn/"
            Datastream: sosa:isMemberOf

Sometimes, the JSON-LD desired for an individual feature in a collection is more complicated than can be achieved by
aliasing properties using a context. In this case, it is possible to specify a Jinja2 template. When ``item_template``
is defined for a feature collection, the json-ld prepared by pygeoapi will be used to render the Jinja2 template
specified by the path. The path specified can be absolute or relative to pygeoapi's template folder. For even more
deployment flexibility, the path can be specified with string interpolation of environment variables.


.. code-block:: yaml

    linked-data:
      item_template: tests/data/base.jsonld
      context:
        - datetime: https://schema.org/DateTime

.. note::
   The template ``tests/data/base.jsonld`` renders the unmodified JSON-LD. For more information on the capacities
   of Jinja2 templates, see :ref:`html-templating`.

Summary
-------

At this point, you have the configuration ready to administer the server.


.. _`YAML`: https://en.wikipedia.org/wiki/YAML
.. _`JSON-LD`: https://json-ld.org
.. _`Google Structured Data Testing Tool`: https://search.google.com/structured-data/testing-tool#url=https%3A%2F%2Fdemo.pygeoapi.io%2Fmaster
.. _`Google Dataset Search`: https://developers.google.com/search/docs/appearance/structured-data/dataset
