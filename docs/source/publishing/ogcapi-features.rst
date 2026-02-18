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
   :header: Provider, property filters/display, resulttype, bbox, datetime, sortby, skipGeometry, domains, CQL, transactions, crs
   :align: left

   `CSV`_,✅/✅,results/hits,✅,❌,❌,✅,❌,❌,❌,✅
   `Elasticsearch`_,✅/✅,results/hits,✅,✅,✅,✅,✅,✅,✅,✅
   `ERDDAP Tabledap Service`_,❌/❌,results/hits,✅,✅,❌,❌,❌,❌,❌,✅
   `ESRI Feature Service`_,✅/✅,results/hits,✅,✅,✅,✅,❌,❌,❌,✅
   `GeoJSON`_,✅/✅,results/hits,✅,❌,❌,✅,❌,❌,❌,✅
   `MongoDB`_,✅/❌,results,✅,✅,✅,✅,❌,❌,❌,✅
   `MySQL`_,✅/✅,results/hits,✅,✅,✅,✅,❌,✅,✅,✅
   `OGR`_,✅/❌,results/hits,✅,❌,❌,✅,❌,❌,❌,✅
   `OpenSearch`_,✅/✅,results/hits,✅,✅,✅,✅,❌,✅,✅,✅
   `Oracle`_,✅/✅,results/hits,✅,❌,✅,✅,❌,❌,❌,✅
   `Parquet`_,✅/✅,results/hits,✅,✅,❌,✅,❌,❌,❌,✅
   `PostgreSQL`_,✅/✅,results/hits,✅,✅,✅,✅,❌,✅,✅,✅
   `SQLiteGPKG`_,✅/❌,results/hits,✅,❌,❌,✅,❌,❌,❌,✅
   `SensorThings API`_,✅/✅,results/hits,✅,✅,✅,✅,❌,❌,✅,✅
   `Socrata`_,✅/✅,results/hits,✅,✅,✅,✅,❌,❌,❌,✅
   `TinyDB`_,✅/✅,results/hits,✅,✅,✅,✅,✅,❌,✅,✅

.. note::
   For more information on CRS transformations, see :ref:`crs`.


Connection examples
-------------------

Below are specific connection examples based on supported providers.

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

.. note::

   For Elasticseach indexes that are password protect, a RFC1738 URL can be used as follows:

   ``data: http://username:password@localhost:9200/ne_110m_populated_places_simple``

   To further conceal authentication credentials, environment variables can be used:

   ``data: http://${MY_USERNAME}:${MY_PASSWORD}@localhost:9200/ne_110m_populated_places_simple``

The ES provider also has the support for the CQL queries as indicated in the table above.

.. seealso::
  :ref:`cql` for more details on how to use Common Query Language (CQL) to filter the collection with specific queries.

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

ESRI Feature Service
^^^^^^^^^^^^^^^^^^^^

To publish an ESRI `Feature Service`_ or `Map Service`_ specify the URL for the service layer in the ``data`` field.

* ``id_field`` will often be ``OBJECTID``, ``objectid``, or ``FID``.
* If the map or feature service is not shared publicly, the ``username`` and ``password`` fields can be set in the
  configuration to authenticate to the service.
* If the map or feature service is self-hosted and not shared publicly, the ``token_service`` and optional ``referer`` fields
  can be set in the configuration to authenticate to the service.

To publish from an ArcGIS online hosted service:

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
         token_service: https://your.server.com/arcgis/sharing/rest/generateToken  # optional URL to your generateToken service
         referer: https://your.server.com  # optional referer, defaults to https://www.arcgis.com if not set

To publish from a self-hosted service that is not publicly accessible, the ``token_service`` field is required:

.. code-block:: yaml

   providers:
       - type: feature
         name: ESRI
         data: https://your.server.com/arcgis/rest/services/your-layer/MapServer/0
         id_field: objectid
         time_field: date_in_your_device_time_zone # Optional time field
         crs: 4326 # Optional crs (default is EPSG:4326)
         username: username # Optional ArcGIS username
         password: password # Optional ArcGIS password
         token_service: https://your.server.com/arcgis/sharing/rest/generateToken # Optional url to your generateToken service
         referer: https://your.server.com # Optional referer, defaults to https://www.arcgis.com if not set

GeoJSON
^^^^^^^

To publish a GeoJSON file, the file must be a valid GeoJSON FeatureCollection.

.. code-block:: yaml

   providers:
       - type: feature
         name: GeoJSON
         data: tests/data/file.json
         id_field: id

MongoDB
^^^^^^^

.. note::
   Requires Python package pymongo

.. note::
   Mongo 5 or greater is supported.

MongoDB (`website <https://www.mongodb.com/>`_) is a powerful and versatile NoSQL database that provides numerous advantages, making it a preferred choice for many applications. One of the main reasons to use MongoDB is its ability to handle large volumes of unstructured data, making it ideal for managing diverse data types such as text, geospatial, and multimedia data. Additionally, MongoDB's flexible document model allows for easy schema evolution, enabling developers to iterate quickly and adapt to changing requirements.

`MongoDB GeoJSON <https://www.mongodb.com/docs/manual/reference/geojson/>`_ support is available, thus a GeoJSON file can be added to MongoDB using following command

`mongoimport --db test -c points --file "path/to/file.geojson" --jsonArray`

Here `test` is the name of database , `points` is the target collection name.

* each document must be a GeoJSON Feature, with a valid geometry.

.. code-block:: yaml

   providers:
       - type: feature
         name: MongoDB
         data: mongodb://localhost:27017/testdb
         collection: testplaces


.. _MySQL:

MySQL
^^^^^

.. note::
   Requires Python packages sqlalchemy, geoalchemy2 and pymysql

Must have MySQL installed.

.. code-block:: yaml

   providers:
       - type: feature
         name: MySQL
         data:
             host: 127.0.0.1
             port: 3306 # Default 3306 if not provided
             dbname: test_geo_app
             user: mysql
             password: mysql
             search_path: [test_geo_app] # Same as dbname
         id_field: locationID
         table: location
         geom_field: locationCoordinates

A number of database connection options can be also configured in the provider in order to adjust properly the sqlalchemy engine client.
These are optional and if not specified, the default from the engine will be used. Please see also `SQLAlchemy docs <https://docs.sqlalchemy.org/en/14/core/engines.html#custom-dbapi-connect-arguments-on-connect-routines>`_.

.. code-block:: yaml

    providers:
       - type: feature
         name: MySQL
         data:
             host: 127.0.0.1
             port: 3306 # Default 3306 if not provided
             dbname: test_geo_app
             user: mysql
             password: mysql
             search_path: [test_geo_app] # Same as dbname
         options:
             # Maximum time to wait while connecting, in seconds.
             connect_timeout: 10
             # Number of *milliseconds* that transmitted data may remain
             # unacknowledged before a connection is forcibly closed.
             tcp_user_timeout: 10000
             # Whether client-side TCP keepalives are used. 1 = use keepalives,
             # 0 = don't use keepalives.
             keepalives: 1
             # Number of seconds of inactivity after which TCP should send a
             # keepalive message to the server.
             keepalives_idle: 5
             # Number of TCP keepalives that can be lost before the client's
             # connection to the server is considered dead.
             keepalives_count: 5
             # Number of seconds after which a TCP keepalive message that is not
             # acknowledged by the server should be retransmitted.
             keepalives_interval: 1
         id_field: locationID
         table: location
         geom_field: locationCoordinates

This provider has support for the CQL queries as indicated in the Provider table above.

.. seealso::
  :ref:`cql` for more details on how to use Common Query Language (CQL) to filter the collection with specific queries.


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

.. _OpenSearch:

OpenSearch
^^^^^^^^^^

.. note::
   Requires Python package opensearch-py

To publish an OpenSearch index, the following are required in your index:

* indexes must be documents of valid GeoJSON Features
* index mappings must define the GeoJSON ``geometry`` as a ``geo_shape``

.. code-block:: yaml

   providers:
       - type: feature
         name: OpenSearch
         editable: true|false  # optional, default is false
         data: http://localhost:9200/ne_110m_populated_places_simple
         id_field: geonameid
         time_field: datetimefield

.. note::

   For OpenSearch indexes that are password protect, a RFC1738 URL can be used as follows:

   ``data: http://username:password@localhost:9200/ne_110m_populated_places_simple``

   To further conceal authentication credentials, environment variables can be used:

   ``data: http://${MY_USERNAME}:${MY_PASSWORD}@localhost:9200/ne_110m_populated_places_simple``

The OpenSearch provider also has the support for the CQL queries as indicated in the table above.

.. seealso::
  :ref:`cql` for more details on how to use Common Query Language (CQL) to filter the collection with specific queries.

.. _Oracle:

Oracle
^^^^^^

.. note::
  Requires Python package oracledb

Connection
""""""""""
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

The provider supports connection over host and port with SID, SERVICE_NAME or TNS_NAME. For TNS naming, the system 
environment variable TNS_ADMIN or the configuration parameter tns_admin must be set.

The providers supports external authentication. At the moment only wallet authentication is implemented.

Sometimes it is necessary to use the Oracle client for the connection. In this case init_oracle_client must be set to True.

SDO options
"""""""""""
.. code-block:: yaml

  providers:
      - type: feature
        name: OracleDB
        data:
            host: 127.0.0.1
            port: 1521
            service_name: XEPDB1
            user: geo_test
            password: geo_test
        id_field: id
        table: lakes
        geom_field: geometry
        title_field: name
        sdo_operator: sdo_relate # defaults to sdo_filter
        sdo_param: mask=touch+coveredby # defaults to mask=anyinteract
        
The provider supports two different SDO operators, sdo_filter and sdo_relate. When not set, the default is sdo_relate!
Further more  it is possible to set the sdo_param option. When sdo_relate is used the default is anyinteraction!
`See Oracle Documentation for details <https://docs.oracle.com/en/database/oracle/oracle-database/23/spatl/spatial-operators-reference.html>`_.

Mandatory properties
""""""""""""""""""""
.. code-block:: yaml

  providers:
      - type: feature
        name: OracleDB
        data:
            host: 127.0.0.1
            port: 1521
            service_name: XEPDB1
            user: geo_test
            password: geo_test
        id_field: id
        table: lakes
        geom_field: geometry
        title_field: name
        mandatory_properties:
        - example_group_id

On large tables it could be useful to disallow a query on the complete dataset. For this reason it is possible to 
configure mandatory properties. When this is activated, the provider throws an exception when the parameter
is not in the query uri.

Extra properties
""""""""""""""""
.. code-block:: yaml

  providers:
      - type: feature
        name: OracleDB
        data:
            host: 127.0.0.1
            port: 1521
            service_name: XEPDB1
            user: geo_test
            password: geo_test
        id_field: id
        table: lakes
        geom_field: geometry
        title_field: name
        extra_properties:
        - "'Here we have ' || name AS tooltip"

Extra properties is a list of strings which are added as fields for data retrieval in the SELECT clauses. They
can be used to return expressions computed by the database.

Session Pooling
"""""""""""""""

Configured using environment variables.

.. code-block:: bash

   export ORACLE_POOL_MIN=2
   export ORACLE_POOL_MAX=10


The ``ORACLE_POOL_MIN`` and ``ORACLE_POOL_MAX`` environment variables are used to trigger session pool creation in the Oracle Provider and the ``DatabaseConnection`` class. Supports auth via user + password or wallet. For an example of the configuration see above at Oracle - Connection. See https://python-oracledb.readthedocs.io/en/latest/api_manual/module.html#oracledb.create_pool for documentation of the ``create_pool`` function.

If none or only one of the environment variables is set, session pooling will not be activated and standalone connections are established at every request.


Extra_params
""""""""""""
The Oracle provider allows for additional parameters that can be passed in the request. It allows for the processing of additional parameters that are not defined in the ``pygeoapi-config.yml`` to be passed to a custom SQL-Manipulator-Plugin. An example use case of this is advanced filtering without exposing the filtered columns like follows ``.../collections/some_data/items?is_recent=true``. The ``SqlManipulator`` plugin's ``process_query`` method would receive ``extra_params = {'is_recent': 'true'}`` and could dynamically add a custom condition to the SQL query, like ``AND SYSDATE - create_date < 30``.

The ``include_extra_query_parameters`` has to be set to ``true`` for the collection in ``pygeoapi-config.yml``. This ensures that the additional request parameters (e.g. ``is_recent=true``) are not discarded. 


Custom SQL Manipulator Plugin
"""""""""""""""""""""""""""""
The provider supports a SQL-Manipulator-Plugin class. With this, the SQL statement could be manipulated. This is
useful e.g. for authorization at row level or manipulation of the explain plan with hints. 

More information and examples about this feature can be found in ``tests/provider/test_oracle_provider.py``.

.. _Parquet:

Parquet
^^^^^^^

.. note::
   Requires Python package pyarrow

To publish a GeoParquet file (with a geometry column) the geopandas package is also required.

.. note::
   Reading data directly from a public s3 bucket is also supported.

.. code-block:: yaml

   providers:
      - type: feature
        name: Parquet
        data: 
          source: ./tests/data/parquet/random.parquet
        id_field: id
        time_field: time
        x_field:
          - minlon
          - maxlon
        y_field: 
          - minlat
          - maxlat

For GeoParquet data, the `x_field` and `y_field` must be specified in the provider definition,
and they must be arrays of two column names that contain the x and y coordinates of the
bounding box of each geometry. If the geometries in the data are all points, the `x_field` and `y_field`
can be strings instead of arrays and refer to a single column each.

.. _PostgreSQL:

PostgreSQL
^^^^^^^^^^

.. note::
   Requires Python packages sqlalchemy, geoalchemy2 and psycopg2-binary

Must have PostGIS installed.

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
         count: true # Optional; Default true; Enable/disable count for improved performance.

This can be represented as a connection dictionary or as a connection string as follows:

.. code-block:: yaml

   providers:
       - type: feature
         name: PostgreSQL
         data: postgresql://postgres:postgres@127.0.0.1:3010/test
         id_field: osm_id
         table: hotosm_bdi_waterways
         geom_field: foo_geom

A number of database connection options can be also configured in the provider in order to adjust properly the sqlalchemy engine client.
These are optional and if not specified, the default from the engine will be used. Please see also `SQLAlchemy docs <https://docs.sqlalchemy.org/en/14/core/engines.html#custom-dbapi-connect-arguments-on-connect-routines>`_.

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
         options:
             # Maximum time to wait while connecting, in seconds.
             connect_timeout: 10
             # Number of *milliseconds* that transmitted data may remain
             # unacknowledged before a connection is forcibly closed.
             tcp_user_timeout: 10000
             # Whether client-side TCP keepalives are used. 1 = use keepalives,
             # 0 = don't use keepalives.
             keepalives: 1
             # Number of seconds of inactivity after which TCP should send a
             # keepalive message to the server.
             keepalives_idle: 5
             # Number of TCP keepalives that can be lost before the client's
             # connection to the server is considered dead.
             keepalives_count: 5
             # Number of seconds after which a TCP keepalive message that is not
             # acknowledged by the server should be retransmitted.
             keepalives_interval: 1
         id_field: osm_id
         table: hotosm_bdi_waterways
         geom_field: foo_geom
         count: true # Optional; Default true; Enable/disable count for improved performance.

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
         count: true # Optional; Default true; Enable/disable count for improved performance.

This is what a configuration for `Google Cloud SQL`_ connection looks like. The ``host``
block contains the necessary socket connection information.

This provider has support for the CQL queries as indicated in the Provider table above.

.. seealso::
  :ref:`cql` for more details on how to use Common Query Language (CQL) to filter the collection with specific queries.

SQLiteGPKG
^^^^^^^^^^

.. note::
   Requires Spatialite installation

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

Additionally there is the optional field ``expand``. This field will overwrite the default
pygeoapi expand behavior and instead implement the configured expand strategy. This is
particularly useful if you have Datastreams with many observations.

.. code-block:: yaml

   providers:
       - type: feature
         name: SensorThings
         data: https://sensorthings-wq.brgm-rec.fr/FROST-Server/v1.0/
         uri_field: uri
         entity: Datastreams
         time_field: phenomenonTime
         intralink: true
         expand: Thing/Locations,Observations($select=result,phenomenonTime;$orderby=phenomenonTime desc;$top=1)

If all three entities are configured, the STA provider will represent a complete STA
endpoint as OGC-API feature collections. The ``Things`` features will include links
to the associated features in the ``Datastreams`` feature collection, and the
``Observations`` features will include links to the associated features in the
``Datastreams`` feature collection. Examples with three entities configured
are included in the docker examples for SensorThings.

Socrata
^^^^^^^

To publish a `Socrata Open Data API (SODA)`_ endpoint, pygeoapi heavily relies on `sodapy`_.


* ``data`` is the domain of the SODA endpoint.
* ``resource_id`` is the 4x4 resource id pattern.
* ``geom_field`` is required for bbox queries to work.
* ``token`` is optional and can be included in the configuration to pass
  an `app token <https://dev.socrata.com/docs/app-tokens.html>`_ to Socrata.


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


TinyDB
^^^^^^

.. note::
   Requires Python package tinydb

To publish a TinyDB (`see website <https://tinydb.readthedocs.io>`_) index, the following are required in your index:

* indexes must be documents of valid GeoJSON Features

.. code-block:: yaml

   providers:
       - type: feature
         editable: true|false  # optional, default is false
         name: TinyDB
         data: /path/to/file.db
         id_field: identifier
         time_field: datetimefield

.. _including-extra-query-parameters:

Including extra query parameters
--------------------------------

By default, pygeoapi ignores any extra query parameters.  For example, for a given ``.../items`` query, the query key-value pair ``foo1=bar1`` (if ``foo1`` is not a valid property of a given collection) would be ignored by pygeoapi as well as the underlying provider.

To include/accept extra query parameters, the ``include_extra_query_parameters`` directive can be set in provider configuration:

.. code-block:: yaml

   providers:
       - type: feature
         editable: true|false  # optional, default is false
         name: TinyDB
         data: /path/to/file.db
         id_field: identifier
         time_field: datetimefield
         include_extra_query_parameters: true


With the above configuration, pygeoapi will pass ``foo1=bar1`` to the underlying provider.  If the underlying provider does not have ``foo1`` as a queryable property, then an exception will be returned citing an unknown property.

Extra query parameters are useful for custom providers who may wish for specific functionality to be triggered by query parameters that are not bound to a given collection's properties.


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

* queryables on specific properties

  * http://localhost:5000/collections/foo/queryables?properties=title,type

* queryables with current domain values

  * http://localhost:5000/collections/foo/queryables?profile=actual-domain

* queryables on specific properties with current domain values

  * http://localhost:5000/collections/foo/queryables?profile=actual-domain&properties=title,type

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

.. _`Feature Service`: https://enterprise.arcgis.com/en/server/latest/publish-services/windows/what-is-a-feature-service-.htm
.. _`Map Service`: https://enterprise.arcgis.com/en/server/latest/publish-services/windows/what-is-a-map-service.htm
.. _`Google Cloud SQL`: https://cloud.google.com/sql
.. _`OGC API - Features`: https://ogcapi.ogc.org/features
.. _`Socrata Open Data API (SODA)`: https://dev.socrata.com
.. _`sodapy`: https://github.com/xmunoz/sodapy
.. _`Tabledap`: https://coastwatch.pfeg.noaa.gov/erddap/tabledap/documentation.html
.. _`requests`: https://requests.readthedocs.io
