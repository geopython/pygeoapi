.. _ogcapi-maps:

Publishing maps to OGC API - Maps
=================================

`OGC API - Maps`_ provides geospatial data as web maps.

To add data to pygeoapi, you can use the dataset example in :ref:`configuration`
as a baseline and modify accordingly.

Providers
---------

pygeoapi core feature providers are listed below, along with a matrix of supported query
parameters.

.. csv-table::
   :header: Provider, bbox, width/height
   :align: left

   MapScript,,✅,✅
   WMSFacade,,✅,✅


Below are specific connection examples based on supported providers.

Connection examples
-------------------

MapScript
^^^^^^^^^

`MapScript`_ is MapServer's scripting interface to map rendering.

To publish a map via MapScript, the path to data is required, as well as
the layer type (`options.type`).  To style the data, set `options.style`. If
no style is specified, the layer will be rendered with defaults.

MapServer layer types (`options.type`):

- `MS_LAYER_POINT`
- `MS_LAYER_LINE`
- `MS_LAYER_POLYGON`
- `MS_LAYER_RASTER`

Currently supported style files (`options.style`):

- OGC Styled Layer Descriptor (SLD)
- MapServer CLASS includes (i.e. file snippets with CLASS definitions)

.. code-block:: yaml

   providers:
       - type: map 
         name: MapScript
         data: /path/to/data.shp
         options:
             type: MS_LAYER_POINT
             layer: foo_name
             style: ./foo.sld
         format:
            name: png 
            mimetype: image/png

WMSFacade
^^^^^^^^^

To publish a WMS via pygeoapi, the WMS base URL (`data`) and layer name (`options.layer`) is
required.  An optional style name can be defined via `options.style`.

.. code-block:: yaml

   providers:
       - type: map 
         name: WMSFacade
         data: https://demo.mapserver.org/cgi-bin/msautotest
         options:
             layer: world_latlong
             style: default
         format:
               name: png 
               mimetype: image/png


Data visualization examples
---------------------------

* list all collections
  * http://localhost:5000/collections
* overview of dataset
  * http://localhost:5000/collections/foo
* map (default format)
  * http://localhost:5000/collections/foo/map
* map with bbox subset
  * http://localhost:5000/collections/foo/map?bbox=-142,42,-52,84
* map with bbox and temporal subset
  * http://localhost:5000/collections/foo/map?bbox=-142,42,-52,84&datetime=2020-04-10T14:11:00Z
* map with bbox and bbox-crs
  * http://localhost:5000/collections/foo/map?bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F3857&bbox=4.022369384765626%2C50.690447870569436%2C4.681549072265626%2C51.00260125274477&width=800&height=600&transparent

.. _`OGC API - Maps`: https://www.ogc.org/standards/ogcapi-maps
.. _`MapScript`: https://mapserver.org/mapscript/index.html
