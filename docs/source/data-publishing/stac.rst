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

.. code-block:: yaml

   my-stac-resource:
       type: stac-collection
       ...
       provider:
           name: FileSystem
           data: /Users/tomkralidis/Dev/data/gdps
           file_types:
               - .grib2


.. note::
   ``rasterio`` and ``fiona`` are required for describing geospatial files.

Data access examples
--------------------

- STAC root page
  - http://localhost:5000/stac

From here, browse the filesystem accordingly.

.. _`SpatioTemporal Asset Catalog (STAC)`: https://stacspec.org
