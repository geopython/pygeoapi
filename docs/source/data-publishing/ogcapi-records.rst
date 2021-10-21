.. _ogcapi-records:

Publishing metadata to OGC API - Records
========================================

`OGC API - Records`_ provides geospatial data access functionality to vector data.

To add vector data to pygeoapi, you can use the dataset example in :ref:`configuration`
as a baseline and modify accordingly.

Providers
---------

pygeoapi core record providers are listed below, along with a matrix of supported query
parameters.

.. csv-table::
   :header: Provider, properties (filters), resulttype, q, bbox, datetime, sortby, properties (display)
   :align: left

   ElasticsearchCatalogue,✅,results/hits,✅,✅,✅,✅
   TinyDBCatalogue,✅,results/hits,✅,✅,✅,✅


Below are specific connection examples based on supported providers.

Connection examples
-------------------

ElasticsearchCatalogue
^^^^^^^^^^^^^^^^^^^^^^

.. note::
   Elasticsearch 7 or greater is supported.


To publish an Elasticsearch index, the following are required in your index:

- indexes must be documents of valid `OGC API - Records GeoJSON Features`_
- index mappings must define the GeoJSON ``geometry`` as a ``geo_shape``

.. code-block:: yaml

   providers:
       - type: record
         name: ElasticsearchCatalogue
         data: http://localhost:9200/some_metadata_index
         id_field: identifier
         time_field: datetimefield

TinyDBCatalogue
^^^^^^^^^^^^^^^

.. note::
   Elasticsearch 7 or greater is supported.


To publish a TinyDB index, the following are required in your index:

- indexes must be documents of valid `OGC API - Records GeoJSON Features`_

.. code-block:: yaml

   providers:
       - type: record
         name: TinyDBCatalogue
         data: /path/to/file.db
         id_field: identifier
         time_field: datetimefield


Metadata search examples
------------------------

- overview of record collection
  - http://localhost:5000/collections/metadata-records
- queryables
  - http://localhost:5000/collections/foo/queryables
- browse records
  - http://localhost:5000/collections/foo/items
- paging
  - http://localhost:5000/collections/foo/items?startIndex=10&limit=10
- CSV outputs
  - http://localhost:5000/collections/foo/items?f=csv
- query records (spatial)
  - http://localhost:5000/collections/foo/items?bbox=-180,-90,180,90
- query records (attribute)
  - http://localhost:5000/collections/foo/items?propertyname=foo
- query records (temporal)
  - http://localhost:5000/collections/my-metadata/items?datetime=2020-04-10T14:11:00Z
- query features (temporal) and sort ascending by a property (if no +/- indicated, + is assumed)
  - http://localhost:5000/collections/my-metadata/items?datetime=2020-04-10T14:11:00Z&sortby=datetime
- query features (temporal) and sort descending by a property
  - http://localhost:5000/collections/my-metadata/items?datetime=2020-04-10T14:11:00Z&sortby=-datetime
- fetch a specific record
  - http://localhost:5000/collections/my-metadata/items/123

.. _`OGC API - Records`: https://www.ogc.org/standards/ogcapi-records
.. _`OGC API - Records GeoJSON Features`: https://raw.githubusercontent.com/opengeospatial/ogcapi-records/master/core/openapi/schemas/recordGeoJSON.yaml
