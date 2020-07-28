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
   :header: Provider, properties, resulttype, bbox, datetime, sortby
   :align: left

   CSV,✔️ ,results/hits,❌,❌,❌
   Elasticsearch,✔️ ,results/hits,✔️ ,✔️ ,✔️ 
   GeoJSON,✔️ ,results/hits,❌,❌,❌
   MongoDB,✔️ ,results,✔️ ,✔️ ,✔️ 
   OGR,✔️ ,results/hits,✔️ ,❌,❌
   PostgreSQL,✔️ ,results/hits,✔️ ,❌,❌
   SQLiteGPKG,✔️ ,results/hits,✔️ ,❌,❌


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


Elasticsearch
^^^^^^^^^^^^^

.. note::
   Elasticsearch 7 or greater is supported.


To publish an Elasticsearch index, the following are required in your index:

- indexes must be documents of valid GeoJSON Features
- index mappings must define the GeoJSON ``geometry`` as a ``geo_shape``

.. code-block:: yaml

   providers:
       - type: feature
         name: Elasticsearch
         data: http://localhost:9200/ne_110m_populated_places_simple
         id_field: geonameid
         time_field: datetimefield

OGR
^^^

.. todo:: add overview and requirements

MongoDB
^^^^^^^

.. todo:: add overview and requirements

.. code-block:: yaml

   providers:
       - type: feature
         name: MongoDB
         data: mongodb://localhost:27017/testdb
         collection: testplaces


PostgreSQL
^^^^^^^^^^

.. todo:: add overview and requirements

.. code-block:: yaml

   providers:
       - type: feature
         name: PostgreSQL
         data:
             host: 127.0.0.1
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


Data access examples
--------------------

- list all collections
  - http://localhost:5000/collections
- overview of dataset
  - http://localhost:5000/collections/foo
- browse features
  - http://localhost:5000/collections/foo/items
- paging
  - http://localhost:5000/collections/foo/items?startIndex=10&limit=10
- CSV outputs
  - http://localhost:5000/collections/foo/items?f=csv
- query features (spatial)
  - http://localhost:5000/collections/foo/items?bbox=-180,-90,180,90
- query features (attribute)
  - http://localhost:5000/collections/foo/items?propertyname=foo
- query features (temporal)
  - http://localhost:5000/collections/foo/items?datetime=2020-04-10T14:11:00Z
- fetch a specific feature
  - http://localhost:5000/collections/foo/items/123

.. _`OGC API - Features`: https://www.ogc.org/standards/ogcapi-features
