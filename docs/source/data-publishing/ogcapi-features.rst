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
   :header: Provider, property filters/display, resulttype, bbox, datetime, sortby, skipGeometry, CQL
   :align: left

   CSV,✅/✅,results/hits,❌,❌,❌,✅,❌
   Elasticsearch,✅/✅,results/hits,✅,✅,✅,✅,✅
   ESRIFeatureService,✅/✅,results/hits,✅,✅,✅,✅,❌
   GeoJSON,✅/✅,results/hits,❌,❌,❌,✅,❌
   MongoDB,✅/❌,results,✅,✅,✅,✅,❌
   OGR,✅/❌,results/hits,✅,❌,❌,✅,❌
   PostgreSQL,✅/✅,results/hits,✅,❌,✅,✅,❌
   SQLiteGPKG,✅/❌,results/hits,✅,❌,❌,✅,❌
   SensorThingsAPI,✅/✅,results/hits,✅,✅,✅,✅,❌
   Socrata,✅/✅,results/hits,✅,✅,✅,✅,❌


Below are specific connection examples based on supported providers.

Connection examples
-------------------

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
   Elasticsearch 7 or greater is supported.


To publish an Elasticsearch index, the following are required in your index:

* indexes must be documents of valid GeoJSON Features
* index mappings must define the GeoJSON ``geometry`` as a ``geo_shape``

.. code-block:: yaml

   providers:
       - type: feature
         name: Elasticsearch
         data: http://localhost:9200/ne_110m_populated_places_simple
         id_field: geonameid
         time_field: datetimefield

This provider has the support for the CQL queries as indicated in the table above.

.. seealso::
  :ref:`cql` for more details on how to use the Common Query Language to filter the collection with specific queries.


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
         crs: 4326 # Optional crs (default is ESPG:4326)
         username: username # Optional ArcGIS username
         password: password # Optional ArcGIS password


OGR
^^^

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
          id_field: gml_id
          layer: rdinfo:stations
          
.. code-block:: yaml

    providers:
         - type: feature
           name: OGR
           data:
             source_type: ESRIJSON
             source: https://map.bgs.ac.uk/arcgis/rest/services/GeoIndex_Onshore/boreholes/MapServer/0/query?where=BGS_ID+%3D+BGS_ID&outfields=*&orderByFields=BGS_ID+ASC&f=json
             source_srs: EPSG:27700
             target_srs: EPSG:4326
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



MongoDB
^^^^^^^

.. note::
   Mongo 5 or greater is supported.

* each document must be a GeoJSON Feature, with a valid geometry.

.. code-block:: yaml

   providers:
       - type: feature
         name: MongoDB
         data: mongodb://localhost:27017/testdb
         collection: testplaces


PostgreSQL
^^^^^^^^^^

Must have PostGIS installed. 

.. todo:: add overview and requirements

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


SQLiteGPKG
^^^^^^^^^^

.. todo:: add overview and requirements

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
`here <http://docs.opengeospatial.org/is/15-078r6/15-078r6.html#figure_2>`_. 
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
* query features (attribute)
  * http://localhost:5000/collections/foo/items?propertyname=foo
* query features (temporal)
  * http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z
* query features (temporal) and sort ascending by a property (if no +/- indicated, + is assumed)
  * http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z&sortby=+datetime
* query features (temporal) and sort descending by a property
  * http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z&sortby=-datetime
* fetch a specific feature
  * http://localhost:5000/collections/foo/items/123

.. note::
   ``.../items`` queries which return an alternative representation to GeoJSON (which prompt a download)
   will have the response filename matching the collection name and appropriate file extension (e.g. ``my-dataset.csv``)

.. _`OGC API - Features`: https://www.ogc.org/standards/ogcapi-features
