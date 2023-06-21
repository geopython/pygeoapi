.. _ogcapi-features:

Publishing vector data to OGC API - Features
============================================

`OGC API - Features`_ provides geospatial data access functionality to vector data.

To add vector data to pygeoapi, you can use the dataset example in :ref:`configuration`
as a baseline and modify accordingly.

Providers
---------

pygeoapi core feature providers are listed below, along with a matrix of supported query
parameters.


.. csv-table::
   :header: Provider, property filters/display, resulttype, bbox, datetime, sortby, skipGeometry, CQL, transactions, crs
   :align: left

   `CSV`_,✅/✅,results/hits,❌,❌,❌,✅,❌,❌,✅
   `Elasticsearch`_,✅/✅,results/hits,✅,✅,✅,✅,✅,✅,✅
   `ERDDAP Tabledap Service`_,❌/❌,results/hits,✅,✅,❌,❌,❌,❌
   `ESRI Feature Service`_,✅/✅,results/hits,✅,✅,✅,✅,❌,❌,✅
   `GeoJSON`_,✅/✅,results/hits,❌,❌,❌,✅,❌,❌,✅
   `MongoDB`_,✅/❌,results,✅,✅,✅,✅,❌,❌,✅
   `OGR`_,✅/❌,results/hits,✅,❌,❌,✅,❌,❌,✅n
   `PostgreSQL`_,✅/✅,results/hits,✅,✅,✅,✅,✅,❌,✅n
   `SQLiteGPKG`_,✅/❌,results/hits,✅,❌,❌,✅,❌,❌,✅
   `SensorThings API`_,✅/✅,results/hits,✅,✅,✅,✅,❌,❌,✅
   `Socrata`_,✅/✅,results/hits,✅,✅,✅,✅,❌,❌,✅

.. note::

   * All Providers that support `bbox` also support the `bbox-crs` parameter. `bbox-crs` is handled within pygeoapi core.
   * All Providers support the `crs` parameter to reproject (transform) response data. Some, like PostgreSQL and OGR, perform this natively: '✅n'.


Connection examples
-------------------

Below are specific connection examples based on supported providers.
To support `crs` on queries, one needs to configure both a list of supported CRSs, and a 'Storage CRS'.
See also :ref:`crs` and :ref:`configuration`. When no CRS information is configured the
default CRS/'Storage CRS' value http://www.opengis.net/def/crs/OGC/1.3/CRS84 is assumed.
That is: WGS84 with lon,lat axis-ordering as in standard GeoJSON.

CSV
^^^

To publish a CSV file, the file must have columns for x and y geometry
which need to be specified in ``geometry`` section of the ``provider``
definition.

.. code-block:: yaml

   providers:
       - type: feature
         name: CSV
         data: tests/data/obs.csv
         id_field: id
         geometry:
             x_field: long
             y_field: lat
         crs:
             - http://www.opengis.net/def/crs/EPSG/0/28992
             - http://www.opengis.net/def/crs/OGC/1.3/CRS84
             - http://www.opengis.net/def/crs/EPSG/0/4326
         storage_crs: http://www.opengis.net/def/crs/EPSG/0/28992


GeoJSON
^^^^^^^

To publish a GeoJSON file, the file must be a valid GeoJSON FeatureCollection.

.. code-block:: yaml

   providers:
       - type: feature
         name: GeoJSON
         data: tests/data/file.json
         id_field: id

.. _Elasticsearch:

Elasticsearch
^^^^^^^^^^^^^

.. note::
   Requires Python packages elasticsearch and elasticsearch-dsl

.. note::
   Elasticsearch 8 or greater is supported.

To publish an Elasticsearch index, the following are required in your index:

* indexes must be documents of valid GeoJSON Features
* index mappings must define the GeoJSON ``geometry`` as a ``geo_shape``

.. code-block:: yaml

   providers:
       - type: feature
         name: Elasticsearch
         editable: true|false  # optional, default is false
         data: http://localhost:9200/ne_110m_populated_places_simple
         id_field: geonameid
         time_field: datetimefield

This provider has the support for the CQL queries as indicated in the table above.

.. seealso::
  :ref:`cql` for more details on how to use Common Query Language (CQL) to filter the collection with specific queries.


ESRI Feature Service
^^^^^^^^^^^^^^^^^^^^

To publish an ESRI `Feature Service <https://enterprise.arcgis.com/en/server/latest/publish-services/windows/what-is-a-feature-service-.htm>`
or `Map Service <https://enterprise.arcgis.com/en/server/latest/publish-services/windows/what-is-a-map-service.htm>`
specify the URL for the service layer in the ``data`` field.

* ``id_field`` will often be ``OBJECTID``, ``objectid``, or ``FID``.
* If the map or feature service is not shared publicly, the ``username`` and ``password`` fields can be set in the
  configuration to authenticate into the service.

.. code-block:: yaml

   providers:
       - type: feature
         name: ESRI
         data: https://sampleserver5.arcgisonline.com/arcgis/rest/services/NYTimes_Covid19Cases_USCounties/MapServer/0
         id_field: objectid
         time_field: date_in_your_device_time_zone # Optional time field
         crs: 4326 # Optional crs (default is EPSG:4326)
         username: username # Optional ArcGIS username
         password: password # Optional ArcGIS password


OGR
^^^

.. note::
   Requires Python package gdal

`GDAL/OGR <https://gdal.org>`_ supports a wide range of spatial file formats, such as shapefile, dxf, gpx, kml,
but also services such as WFS. Read the full list and configuration options at https://gdal.org/drivers/vector.
Additional formats and features are available via the `virtual format <https://gdal.org/drivers/vector/vrt.html#vector-vrt>`_,
use this driver for example for flat database files (CSV).

The OGR provider requires a recent (3+) version of GDAL to be installed.

.. code-block:: yaml

    providers:
        - type: feature
          name: OGR
          data:
            source_type: ESRI Shapefile
            source: tests/data/dutch_addresses_shape_4326/inspireadressen.shp
            source_options:
              ADJUST_GEOM_TYPE: FIRST_SHAPE
            gdal_ogr_options:
              SHPT: POINT
          id_field: fid
          layer: inspireadressen


.. code-block:: yaml

    providers:
        - type: feature
          name: OGR
          data:
            source_type: WFS
            source: WFS:https://geodata.nationaalgeoregister.nl/rdinfo/wfs?
            source_options:
                VERSION: 2.0.0
                OGR_WFS_PAGING_ALLOWED: YES
                OGR_WFS_LOAD_MULTIPLE_LAYER_DEFN: NO
             gdal_ogr_options:
                GDAL_CACHEMAX: 64
                GDAL_HTTP_PROXY: (optional proxy)
                GDAL_PROXY_AUTH: (optional auth for remote WFS)
                CPL_DEBUG: NO
          crs:
            - http://www.opengis.net/def/crs/OGC/1.3/CRS84
            - http://www.opengis.net/def/crs/EPSG/0/4326
            - http://www.opengis.net/def/crs/EPSG/0/4258
            - http://www.opengis.net/def/crs/EPSG/0/28992
          storage_crs: http://www.opengis.net/def/crs/EPSG/0/28992
          id_field: gml_id
          layer: rdinfo:stations

.. code-block:: yaml

    providers:
         - type: feature
           name: OGR
           data:
             source_type: ESRIJSON
             source: https://map.bgs.ac.uk/arcgis/rest/services/GeoIndex_Onshore/boreholes/MapServer/0/query?where=BGS_ID+%3D+BGS_ID&outfields=*&orderByFields=BGS_ID+ASC&f=json
             source_capabilities:
                 paging: True
             open_options:
                 FEATURE_SERVER_PAGING: YES
             gdal_ogr_options:
                 EMPTY_AS_NULL: NO
                 GDAL_CACHEMAX: 64
                 # GDAL_HTTP_PROXY: (optional proxy)
                 # GDAL_PROXY_AUTH: (optional auth for remote WFS)
                 CPL_DEBUG: NO
           id_field: BGS_ID
           layer: ESRIJSON

.. code-block:: yaml

    providers:
         - type: feature
           name: OGR
           data:
             source_type: PostgreSQL
             source: "PG: host=127.0.0.1 dbname=test user=postgres password=postgres"
           id_field: osm_id
           layer: osm.hotosm_bdi_waterways # Value follows a 'my_schema.my_table' structure
           geom_field: foo_geom

.. note::
   NB: Formerly the config parameters ``source_srs`` and ``target_srs`` could be used to
   transform/reproject the data for every request. Starting with pygeoapi release 0.15.0 these fields are no longer supported.
   Reason is that pygeoapi now supports CRS-handling as per the OGC API Features Standard "Part 2".
   `storage_crs`: is basically the same as `source_crs` but complying with standards (and axis ordering!)
   It should be set to the actual or default CRS of the source data/service. When omitted the default http://www.opengis.net/def/crs/OGC/1.3/CRS84
   if assumed.
   `crs` is an array of supported CRSs, also the same default applies when omitted.
   The `crs` or `bbox-crs` query parameter can now be used and must be present in the `crs` array (or
   the default applies).
   The `crs` query parameter is used as follows:
   e.g. ``http://localhost:5000/collections/foo/items?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992``.


MongoDB
^^^^^^^

.. note::
   Requires Python package pymongo

.. note::
   Mongo 5 or greater is supported.

* each document must be a GeoJSON Feature, with a valid geometry.

.. code-block:: yaml

   providers:
       - type: feature
         name: MongoDB
         data: mongodb://localhost:27017/testdb
         collection: testplaces

.. _Oracle:

Oracle
^^^^^^

.. note::
  Requires Python package oracledb

.. code-block:: yaml

  providers:
      - type: feature
        name: OracleDB
        data:
            host: 127.0.0.1
            port: 1521 # defaults to 1521 if not provided
            service_name: XEPDB1
            # sid: XEPDB1
            user: geo_test
            password: geo_test
            # external_auth: wallet
            # tns_name: XEPDB1
            # tns_admin /opt/oracle/client/network/admin 
            # init_oracle_client: True

        id_field: id
        table: lakes
        geom_field: geometry
        title_field: name
        # sql_manipulator: tests.test_oracle_provider.SqlManipulator
        # sql_manipulator_options:
        #     foo: bar
        # mandatory_properties:
        # - bbox
        # source_crs: 31287 # defaults to 4326 if not provided
        # target_crs: 31287 # defaults to 4326 if not provided

The provider supports connection over host and port with SID or SERVICE_NAME. For TNS naming, the system 
environment variable TNS_ADMIN or the configuration parameter tns_admin must be set.

The providers supports external authentication. At the moment only wallet authentication is implemented.

Sometimes it is necessary to use the Oracle client for the connection. In this case init_oracle_client must be set to True.

The provider supports a SQL-Manipulator-Plugin class. With this, the SQL statement could be manipulated. This is
useful e.g. for authorization at row level or manipulation of the explain plan with hints. For this, the SQL 
statement has three different placeholders which could be replaced: #HINTS#, #WHERE# and #JOIN#.

.. code-block:: sql

  SELECT #HINTS# t1.id, ...
    FROM table t1 #JOIN# 
    #WHERE#
    ORDER BY t1.id ASC
    OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY

Example SQL Manipulator
"""""""""""""""""""""""
.. code-block:: python

  class SqlManipulator:
    def process(
        self,
        db,
        sql_query,
        bind_variables,
        sql_manipulator_options,
        bbox,
        source_crs,
        properties,
    ):
        sql = "ID = 10 AND :foo != :bar"

        if sql_query.find(" WHERE ") == -1:
            sql_query = sql_query.replace("#WHERE#", f" WHERE {sql}")
        else:
            sql_query = sql_query.replace("#WHERE#", f" AND {sql}")

        bind_variables = {
            **bind_variables,
            "foo": "foo",
            "bar": sql_manipulator_options.get("foo"),
        }

        return sql_query, bind_variables

.. _PostgreSQL:

PostgreSQL
^^^^^^^^^^

.. note::
   Requires Python packages sqlalchemy, geoalchemy2 and psycopg2-binary

Must have PostGIS installed.

.. note::
   Geometry must be using EPSG:4326

.. code-block:: yaml

   providers:
       - type: feature
         name: PostgreSQL
         data:
             host: 127.0.0.1
             port: 3010 # Default 5432 if not provided
             dbname: test
             user: postgres
             password: postgres
             search_path: [osm, public]
         id_field: osm_id
         table: hotosm_bdi_waterways
         geom_field: foo_geom

The PostgreSQL provider is also able to connect to Cloud SQL databases.

.. code-block:: yaml

   providers:
       - type: feature
         name: PostgreSQL
         data:
             host: /cloudsql/INSTANCE_CONNECTION_NAME # e.g. 'project:region:instance'
             dbname: reference
             user: postgres
             password: postgres
         id_field: id
         table: states

This is what a configuration for `Google Cloud SQL`_ connection looks like. The ``host``
block contains the necessary socket connection information.

This provider has support for the CQL queries as indicated in the Provider table above.

.. seealso::
  :ref:`cql` for more details on how to use Common Query Language (CQL) to filter the collection with specific queries.

SQLiteGPKG
^^^^^^^^^^

.. note::
   Requries Spatialite installation

SQLite file:

.. code-block:: yaml

   providers:
       - type: feature
         name: SQLiteGPKG
         data: ./tests/data/ne_110m_admin_0_countries.sqlite
         id_field: ogc_fid
         table: ne_110m_admin_0_countries


GeoPackage file:

.. code-block:: yaml

   providers:
       - type: feature
         name: SQLiteGPKG
         data: ./tests/data/poi_portugal.gpkg
         id_field: osm_id
         table: poi_portugal


SensorThings API
^^^^^^^^^^^^^^^^

The STA provider is capable of creating feature collections from OGC SensorThings
API endpoints. Three of the STA entities are configurable: Things, Datastreams, and
Observations. For a full description of the SensorThings entity model, see
`here <https://docs.ogc.org/is/15-078r6/15-078r6.html#figure_2>`_.
For each entity of ``Things``, pygeoapi will expand all entities directly related to
the ``Thing``, including its associated ``Location``, from which the
geometry for the feature collection is derived. Similarly, ``Datastreams`` are expanded to
include the associated ``Thing``, ``Sensor`` and ``ObservedProperty``.

The default id_field is ``@iot.id``. The STA provider adds one required field,
``entity``, and an optional field, ``intralink``. The ``entity`` field refers to
which STA entity to use for the feature collection. The ``intralink`` field controls
how the provider is acted upon by other STA providers and is by default, False.
If ``intralink`` is true for an adjacent STA provider collection within a
pygeoapi instance, the expanded entity is instead represented by an intra-pygeoapi
link to the other entity or it's ``uri_field`` if declared.

.. code-block:: yaml

   providers:
       - type: feature
         name: SensorThings
         data: https://sensorthings-wq.brgm-rec.fr/FROST-Server/v1.0/
         uri_field: uri
         entity: Datastreams
         time_field: phenomenonTime
         intralink: true

If all three entities are configured, the STA provider will represent a complete STA
endpoint as OGC-API feature collections. The ``Things`` features will include links
to the associated features in the ``Datastreams`` feature collection, and the
``Observations`` features will include links to the associated features in the
``Datastreams`` feature collection. Examples with three entities configured
are included in the docker examples for SensorThings.

Socrata
^^^^^^^

To publish a `Socrata Open Data API (SODA) <https://dev.socrata.com/>` endpoint, pygeoapi heavily
relies on `sodapy <https://github.com/xmunoz/sodapy>`.


* ``data`` is the domain of the SODA endpoint.
* ``resource_id`` is the 4x4 resource id pattern.
* ``geom_field`` is required for bbox queries to work.
* ``token`` is optional and can be included in the configuration to pass
  an `app token <https://dev.socrata.com/docs/app-tokens.html>` to Socrata.


.. code-block:: yaml

   providers:
       - type: feature
         name: Socrata
         data: https://soda.demo.socrata.com/
         resource_id: emdb-u46w
         id_field: earthquake_id
         geom_field: location
         time_field: datetime # Optional time_field for datetime queries
         token: my_token # Optional app token


.. _ERDDAP Tabledap Service:

ERDDAP Tabledap Service
^^^^^^^^^^^^^^^^^^^^^^^

.. note::
   Requires Python package `requests`_

To publish from an ERDDAP `Tabledap`_ service, the following are required in your index:

.. code-block:: yaml

   providers:
       - type: feature
         name: ERDDAPTabledap
         data: http://osmc.noaa.gov/erddap/tabledap/OSMC_Points
         id_field: PLATFORM_CODE
         time_field: time
         options:
             filters: "&parameter=\"SLP\"&platform!=\"C-MAN%20WEATHER%20STATIONS\"&platform!=\"TIDE GAUGE STATIONS (GENERIC)\""
             max_age_hours: 12


.. note::
   If the ``datetime`` parameter is passed by the client, this overrides the ``options.max_age_hours`` setting.

Controlling the order of properties
-----------------------------------

It is possible to control the order and which properties are exposed/unexposed for any supported feature provider using ``properties`` key within a provider definition, see the example below:

.. code-block:: yaml

   properties:
       - waterway
       - depth
       - name


Data access examples
--------------------

* list all collections
  * http://localhost:5000/collections
* overview of dataset
  * http://localhost:5000/collections/foo
* queryables
  * http://localhost:5000/collections/foo/queryables
* browse features
  * http://localhost:5000/collections/foo/items
* paging
  * http://localhost:5000/collections/foo/items?offset=10&limit=10
* CSV outputs
  * http://localhost:5000/collections/foo/items?f=csv
* query features (spatial)
  * http://localhost:5000/collections/foo/items?bbox=-180,-90,180,90
* query features (spatial with bbox-crs)
  * http://localhost:5000/collections/foo/items?bbox=120000,450000,130000,460000&bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992
* query features (attribute)
  * http://localhost:5000/collections/foo/items?propertyname=foo
* query features (temporal)
  * http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z
* query features (temporal) and sort ascending by a property (if no +/- indicated, + is assumed)
  * http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z&sortby=+datetime
* query features (temporal) and sort descending by a property
  * http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z&sortby=-datetime
* query features in a given (and supported) CRS
  * http://localhost:5000/collections/foo/items?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F32633
* query features in a given bounding BBOX and return in given CRS
  * http://localhost:5000/collections/foo/items?bbox=120000,450000,130000,460000&bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F32633
* fetch a specific feature
  * http://localhost:5000/collections/foo/items/123
* fetch a specific feature in a given (and supported) CRS
  * http://localhost:5000/collections/foo/items/123?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F32633

.. note::
   when no ``crs`` and/or ``bbox-crs`` is provided, the default CRS http://www.opengis.net/def/crs/OGC/1.3/CRS84 (WGS84 in lon, lat ordering) is assumed.
   pygeoapi may perform the necessary transformations if the ``storage_crs`` differs from this default. Features are then always returned in
   that default CRS (as per the GeoJSON Standard).
   In all cases, weather or not these query parameters are supplied, the HTTP Header ``Content-Crs`` denotes the CRS of the Feature(s) in the response.

.. note::
   ``.../items`` queries which return an alternative representation to GeoJSON (which prompt a download)
   will have the response filename matching the collection name and appropriate file extension (e.g. ``my-dataset.csv``)

.. note::
   provider `id_field` values support slashes (i.e. ``my/cool/identifier``). The client request would then
   be responsible for encoding the identifier accordingly (i.e. ``http://localhost:5000/collections/foo/items/my%2Fcool%2Fidentifier``)

.. _`Google Cloud SQL`: https://cloud.google.com/sql
.. _`OGC API - Features`: https://www.ogc.org/standards/ogcapi-features
.. _`Tabledap`: https://coastwatch.pfeg.noaa.gov/erddap/tabledap/documentation.html
.. _`requests`: https://requests.readthedocs.io
