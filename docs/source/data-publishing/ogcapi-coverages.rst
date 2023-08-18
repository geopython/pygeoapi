.. _ogcapi-coverages:

Publishing raster data to OGC API - Coverages
=============================================

`OGC API - Coverages`_ provides geospatial data access functionality to raster data.

To add raster data to pygeoapi, you can use the dataset example in :ref:`configuration`
as a baseline and modify accordingly.

Providers
---------

pygeoapi core feature providers are listed below, along with a matrix of supported query
parameters.

.. csv-table::
   :header: Provider, properties, subset, bbox, datetime, scale-size, scale-factor, scale-axes
   :align: left

   :ref:`Rasterio<rasterio-provider>`,✅,✅,✅,❌,❌,❌,❌
   :ref:`Xarray<xarray-provider>`,✅,✅,✅,✅,❌,❌,❌


Below are specific connection examples based on supported providers.

Connection examples
-------------------

.. _rasterio-provider:

Rasterio
^^^^^^^^

.. note::
   Requires Python package Rasterio

The `Rasterio`_ provider plugin reads and extracts any data that Rasterio is
capable of handling.

.. code-block:: yaml

   providers:
       - type: coverage
         name: rasterio
         data: tests/data/CMC_glb_TMP_TGL_2_latlon.15x.15_2020081000_P000.grib2
         options:  # optional creation options
             DATA_ENCODING: COMPLEX_PACKING
         format:
             name: GRIB
             mimetype: application/x-grib2

.. note::
   The Rasterio provider ``format.name`` directive **requires** a valid
   `GDAL raster driver short name`_.

The `Rasterio`_ provider supports multiple output encodings for coverage data,
which can be different from the native format or CoverageJSON, as long as they
are compatible with the native format (e.g. data types, bit depth, file size
limit). In order, to allow for multiple output encodings, one can configure the
`Rasterio`_ provider as follows:

.. code-block:: yaml

    - type: coverage
      name: rasterio
      data: tests/data/CMC_glb_TMP_TGL_2_latlon.15x.15_2020081000_P000.grib2
      storage_format: # native format
          name: GRIB # required
          mimetype: application/x-grib2 # required
          valid_output_format: True/False # optional, default True
          # Note: options were moved inside the storage_format block
          options: # optional options (i.e. GDAL creation)
              DATA_ENCODING: COMPLEX_PACKING
      # list of other formats supported for export
      format:
          # first additional format
          - name: GTiff # required
            mimetype: image/tiff # required
            options: # optional options (i.e. GDAL creation)
                TILED: YES
		BLOCKXSIZE: 256
		BLOCKYSIZE: 256
          # second additional format
          - name: ... # required
            mimetype: ... # required
            options: # optional options (i.e. GDAL creation)
                opt1_name: opt1_value
                opt2_name: opt2_value
                ...
          ...

This way of configuring the `Rasterio`_ provider can also be used to publish a
coverage dataset made up of multiple data files in a single collection, as long
as they can be indexed in a single GDAL reable file. One can use the `GDAL
virtual format`_ to create a virtual dataset composed from multiple data files
(see https://gdal.org/programs/gdalbuildvrt.html), as data source for the
service:

.. code-block:: yaml

    - type: coverage
      name: rasterio
      data: /path/to/coverage/virtual/dataset.vrt
      storage_format:
          name: VRT
          mimetype: xml/vrt
          valid_output_format: False # not interesting for end-users
      # list of other formats supported for export
      format:
          - name: GTiff
            mimetype: image/tiff


.. _xarray-provider:

xarray
^^^^^^

.. note::
   Requires Python package Xarray

The `Xarray`_ provider plugin reads and extracts `NetCDF`_ and `Zarr`_ data.

.. code-block:: yaml

   providers:
       - type: coverage
         name: xarray
         data: tests/data/coads_sst.nc
         # optionally specify x/y/time fields, else provider will attempt
         # to derive automagically
         x_field: lat
         x_field: lon
         time_field: time
         format:
            name: netcdf
            mimetype: application/x-netcdf

   providers:
       - type: coverage
         name: xarray
         data: tests/data/analysed_sst.zarr
         format:
            name: zarr
            mimetype: application/zip

.. note::
   `Zarr`_ files are directories with files and subdirectories.  Therefore
   a zip file is returned upon request for said format.

Data access examples
--------------------

* list all collections
  * http://localhost:5000/collections
* overview of dataset
  * http://localhost:5000/collections/foo
* coverage rangetype
  * http://localhost:5000/collections/foo/coverage/rangetype
* coverage domainset
  * http://localhost:5000/collections/foo/coverage/domainset
* coverage access via CoverageJSON (default)
  * http://localhost:5000/collections/foo/coverage?f=json
* coverage access via native format or other supported output formats
  (as defined in ``provider.format.name`` or ``provider.storage_format.name``)
  * http://localhost:5000/collections/foo/coverage?f=GRIB
* coverage access with comma-separated properties
  * http://localhost:5000/collections/foo/coverage?properties=1,3
* coverage access with subsetting
  * http://localhost:5000/collections/foo/coverage?subset=lat(10:20)&subset=long(10:20)
* coverage with bbox
  * http://localhost:5000/collections/foo/coverage?bbox=10,10,20,20
* coverage with bbox and bbox CRS
  * http://localhost:5000/collections/foo/coverage?bbox=-8794239.772668611,5311971.846945471,-8348961.809495518,5621521.486192066&bbox=crs=3857

.. note::
   ``.../coverage`` queries which return an alternative representation to CoverageJSON (which prompt a download)
   will have the response filename matching the collection name and appropriate file extension (e.g. ``my-dataset.nc``)

.. _`OGC API - Coverages`: https://github.com/opengeospatial/ogcapi-coverages
.. _`Rasterio`: https://rasterio.readthedocs.io
.. _`Xarray`: https://docs.xarray.dev/en/stable
.. _`NetCDF`: https://en.wikipedia.org/wiki/NetCDF
.. _`Zarr`: https://zarr.readthedocs.io/en/stable
.. _`GDAL raster driver short name`: https://gdal.org/drivers/raster/index.html
.. _`GDAL virtual format`: https://gdal.org/drivers/raster/vrt.html
