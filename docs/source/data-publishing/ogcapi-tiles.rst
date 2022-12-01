.. _ogcapi-tiles:

Publishing map tiles to OGC API - Tiles
=======================================

`OGC API - Tiles`_ provides access to geospatial data in the form of tiles
(map, vector, etc.).

pygeoapi can publish tiles from local or remote data sources (including cloud
object storage or a tile service). To integrate tiles from a local data source, it is assumed
that a directory tree of static tiles has been created on disk.  Examples of
tile generation software include (but are not limited to):

* `MapProxy`_
* `tippecanoe`_

The remote data sources can be an external service like Elasticsearch, read from a generic url template.

.. note::
   Currently, the url template only supports the formats: `/{z}/{x}/{y}` or `/{z}/{y}/{x}`. 
   If you have a different use case, feel free to file an `issue <https://github.com/geopython/pygeoapi/issues>`_.  

Providers
---------

pygeoapi core tile providers are listed below, along with supported storage types.

.. csv-table::
   :header: Provider, local, remote
   :align: left

   MVT,✅,✅


Below are specific connection examples based on supported providers.

Connection examples
-------------------

MVT
^^^

The MVT provider plugin provides access to `Mapbox Vector Tiles`_.

This code block shows how to configure pygeoapi to read Mapbox vector tiles, from disk or from an url.

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT 
         data: tests/data/tiles/ne_110m_lakes  # local directory tree
         # data: http://localhost:9000/ne_110m_lakes/{z}/{x}/{y}.pbf # tiles stored on a Minio bucket
         options:
             metadata_format: raw # default | tilejson
             zoom:
                 min: 0
                 max: 5
             schemes:
                 - WorldCRS84Quad
         format:
             name: pbf 
             mimetype: application/vnd.mapbox-vector-tile

This code block shows how to configure pygeoapi to read Mapbox vector tiles, from an Elasticsearch endpoint.

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT 
         data: http://localhost:9200/ne_110m_populated_places_simple2/_mvt/geometry/{z}/{x}/{y}?grid_precision=0
         # if you don't use precision 0, you will be requesting for aggregations which are not supported in the 
         # free version of elastic
         options:
             metadata_format: raw # default | tilejson
             zoom:
                 min: 0
                 max: 5
             schemes:
                 - WorldCRS84Quad
         format:
             name: pbf 
             mimetype: application/vnd.mapbox-vector-tile

Data access examples
--------------------

* list all collections
  * http://localhost:5000/collections
* overview of dataset
  * http://localhost:5000/collections/foo
* overview of dataset tiles
  * http://localhost:5000/collections/foo/tiles
* tile matrix metadata
  * http://localhost:5000/collections/lakes/tiles/WorldCRS84Quad/metadata
* tiles URI template
  * `http://localhost:5000/collections/lakes/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}?f=mvt <http://localhost:5000/collections/lakes/tiles/{tileMatrixSetId}/{tileMatrix}/{tileRow}/{tileCol}?f=mvt>`_


.. _`OGC API - Tiles`: https://github.com/opengeospatial/ogcapi-tiles
.. _`MapProxy`: https://mapproxy.org
.. _`tippecanoe`: https://github.com/mapbox/tippecanoe
.. _`Mapbox Vector Tiles`: https://docs.mapbox.com/vector-tiles/reference
