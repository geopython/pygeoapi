.. _stac:

Publishing files to a SpatioTemporal Asset Catalog
==================================================

The `SpatioTemporal Asset Catalog (STAC)`_ specification provides an easy approach
for describing geospatial assets.  STAC is typically implemented for imagery and
other raster data.

pygeoapi implements STAC as an geospatial file browser through the FileSystem provider,
supporting any level of file/directory nesting/hierarchy.

Configuring STAC in pygeoapi is done by simply pointing the ``data`` provider property
to the given directory and specifying allowed file types:

Connection examples
-------------------

.. code-block:: yaml

   my-stac-resource:
       type: stac-collection
       ...
       providers:
           - type: stac
             name: FileSystem
             data: /Users/tomkralidis/Dev/data/gdps
             file_types:
                 - .grib2


.. note::
   ``rasterio`` and ``fiona`` are required for describing geospatial files.

pygeometa metadata control files
--------------------------------

pygeoapi's STAC filesystem fuctionality supports `pygeometa`_ MCF files residing
in the same directory as data files.  If an MCF file is found, it will be used
as part of generating the STAC item metadata (e.g. a file named ``birds.csv``
having an associated ``birds.yml`` file).  If no MCF file is found, then
pygeometa will generate the STAC item metadata from configuration and by
reading the data's properties.

Publishing ESRI Shapefiles
--------------------------

ESRI Shapefile publishing requires to specify all required component file extensions
(``.shp``, ``.shx``, ``.dbf``) with the provider ``file_types`` option.

Data access examples
--------------------

* STAC root page
  * http://localhost:5000/stac

From here, browse the filesystem accordingly.

.. _`SpatioTemporal Asset Catalog (STAC)`: https://stacspec.org
.. _`pygeometa`: https://geopython.github.io/pygeometa
