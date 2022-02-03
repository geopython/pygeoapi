.. _ogcapi-tiles:

Publishing map tiles to OGC API - Tiles
=======================================

`OGC API - Tiles`_ provides access to geospatial data in the form of tiles
(map, vector, etc.).

pygeoapi can publish tiles from local or remote data sources (including cloud
object storage).  To integrate tiles from a local data source, it is assumed
that a directory tree of static tiles has been created on disk.  Examples of
tile generation software include (but are not limited to):

* `MapProxy`_
* `tippecanoe`_

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

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT 
         data: tests/data/tiles/ne_110m_lakes  # local directory tree
         # data: https://example.org/ne_110m_lakes/{z}/{x}/{y}.pbf
         metadata: https://example.org/ne_110m_lakes/metadata.json # https://example.org/ne_110m_lakes.json
         options:
             metadata_format: raw # default | tilejson
             bounds: [-7.733181,49.863063,1.763249,60.860926]
             zoom:
                 min: 0
                 max: 5
             schemes:
                 - WebMercatorQuad
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
