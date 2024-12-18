.. _ogcapi-tiles:

Publishing tiles to OGC API - Tiles
=======================================

`OGC API - Tiles`_ provides access to geospatial data in the form of tiles
(map, vector, coverage, etc.).

pygeoapi can publish tiles from local or remote data sources (including cloud
object storage or a tile service).

Providers
---------

pygeoapi core tile providers are listed below, along with supported features.

.. csv-table::
   :header: Provider, rendered on-the-fly, properties, WebMercatorQuad, WorldCRS84Quad, raster, vector
   :align: left

   `MVT-tippecanoe`_,❌,✅,✅,❌,❌,✅
   `MVT-elastic`_,✅,✅,✅,❌,❌,✅
   `MVT-proxy`_,❓,❓,❓,❓,❌,✅
   `WMTSFacade`_,✅,❌,✅,✅,✅,❌

Below are specific connection examples based on supported providers.

Connection examples
-------------------

MVT-tippecanoe
^^^^^^^^^^^^^^

This provider gives support to serving tiles generated using `Mapbox Tippecanoe <https://github.com/mapbox/tippecanoe>`_.
The tiles can be integrated from a path on disk, or from a static url (e.g.: from an S3 or MinIO bucket).
In both cases, they have to be rendered before using pygeoapi.

This code block shows how to configure pygeoapi to read Mapbox vector tiles generated with tippecanoe, from disk or a URL.

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT-tippecanoe
         data: tests/data/tiles/ne_110m_lakes  # local directory tree
         # data: http://localhost:9000/ne_110m_lakes/{z}/{x}/{y}.pbf # tiles stored on a MinIO bucket
         options:
             zoom:
                 min: 0
                 max: 5
        # MVT-elastic always uses WebMercatorQuad tiling scheme
         format:
             name: pbf
             mimetype: application/vnd.mapbox-vector-tile

.. tip::

   In the diving into pygeoapi workshop `OGC API - Tiles Exercise <https://dive.pygeoapi.io/publishing/ogcapi-tiles/#publish-pre-rendered-vector-tiles>`_, detailed instructions can be found on how to generate tiles using tippecanoe and integrate them into pygeoapi.

MVT-elastic
^^^^^^^^^^^

This provider gives support to serving tiles generated using `Elasticsearch <https://www.elastic.co/>`_.
These tiles are rendered on-the-fly using the `Elasticsearch Vector tile search API <https://www.elastic.co/guide/en/elasticsearch/reference/current/search-vector-tile-api.html>`_.
In order to use it, the only requirement is to have the data stored in an Elasticsearch index.

This code block shows how to configure pygeoapi to read Mapbox vector tiles from an Elasticsearch endpoint.

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT-elastic
         data: http://localhost:9200/ne_110m_populated_places_simple2/_mvt/geometry/{z}/{x}/{y}?grid_precision=0
         # if you don't use precision 0, you will be requesting for aggregations which are not supported in the
         # free version of elastic
         options:
             zoom:
                 min: 0
                 max: 5
        # MVT-elastic always uses WebMercatorQuad tiling scheme
         format:
             name: pbf
             mimetype: application/vnd.mapbox-vector-tile

.. tip::
   On `this tutorial <https://dive.pygeoapi.io/publishing/ogcapi-tiles/#publish-vector-tiles-from-elasticsearch>`_  you can find detailed instructions on publish tiles stored in an Elasticsearch endpoint.

MVT-proxy
^^^^^^^^^

This provider gives support to serving tiles from a generic tiles provider `{z}/{x}/{y}`.

For example, you can get and publish tiles from PostGIS providers like `pg_tileserver <https://github.com/CrunchyData/pg_tileserv>`_
or `martin <https://github.com/maplibre/martin>`_. Both of them render tiles on the fly and provide properties.

Following block shows how to configure pygeoapi to read Mapbox vector tiles from pg_tileserver endpoint.

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT-proxy
         data: http://localhost:7800/public.ne_50m_admin_0_countries/{z}/{x}/{y}.mvt
            options:
              zoom:
                min: 0
                max: 15
              schemes:
                - WebMercatorQuad # this option is needed in the MVT-proxy provider
         format:
             name: pbf
             mimetype: application/vnd.mapbox-vector-tile

Following code block shows how to configure pygeoapi to read Mapbox vector tiles from martin endpoint.

.. code-block:: yaml

   providers:
       - type: tile
         name: MVT-proxy
         data: http://localhost:3000/ne_50m_admin_0_countries/{z}/{x}/{y}
         options:
             zoom:
                 min: 0
                 max: 15
             schemes:
                - WebMercatorQuad
         format:
             name: pbf
             mimetype: application/vnd.mapbox-vector-tile


WMTSFacade
^^^^^^^^^^

This provider gives support to serving map tiles generated using a WMTS.

It is important that the WMTS provides a tile matrix set that matches exactly one of the configured schemes in pygeoapi.
Currently only `WebMercatorQuad` and `WorldCRS84Quad` are available in pygeopi.

This code block shows how to configure pygeoapi to read map tiles from a WMTS.

.. code-block:: yaml

   providers:
       - type: tile
         name: WMTSFacade
         data: https://emotional.byteroad.net/geoserver/gwc/service/wmts
         format:
             name: png  # png or jpeg
             mimetype: image/png
         options:
             wmts_layer: camb:hex350_grid_mental_1920 # the layer name of the wmts
             wmts_tile_matrix_set: WebMercatorQuad  # the name of the tile matrix set of the wmts.
             scheme: WebMercatorQuad  # the aligning scheme in pygeoapi.
             zoom:
                 min: 0
                 max: 20

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
  


.. _`OGC API - Tiles`: https://ogcapi.ogc.org/tiles
.. _`tippecanoe`: https://github.com/mapbox/tippecanoe
.. _`Elasticsearch`: https://www.elastic.co/
.. _`Mapbox Vector Tiles`: https://docs.mapbox.com/data/tilesets/guides/vector-tiles-introduction/
