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
   :header: Provider, properties, subset, bbox, datetime
   :align: left

   :ref:`Rasterio<rasterio-provider>`,✅,✅,✅,✅
   :ref:`Xarray<xarray-provider>`,✅,✅,✅,✅


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
         x_field: lon
         y_field: lat
         time_field: time
         # optionally specify the coordinate reference system of your dataset
         # else pygeoapi assumes it is WGS84 (EPSG:4326).
         storage_crs: 4326
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

.. note::
   When referencing `NetCDF`_ or `Zarr`_ data stored in an S3 bucket, 
   be sure to provide the full S3 URL. Any parameters required to open the dataset
   using fsspec can be added to the config file under `options` and `s3`.

.. note::
   When providing a `storage_crs` value in the xarray configuration, specify the 
   coordinate reference system using any valid input for 
   `pyproj.CRS.from_user_input`_. 

Data access examples
--------------------

* list all collections

  * http://localhost:5000/collections
  
* overview of dataset

  * http://localhost:5000/collections/foo
  
* schema of dataset

  * http://localhost:5000/collections/foo/schema
  
* coverage access via CoverageJSON (default)

  * http://localhost:5000/collections/foo/coverage?f=json
  
* coverage access via native format (as defined in ``provider.format.name``)

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

.. _`OGC API - Coverages`: https://ogcapi.ogc.org/coverages
.. _`Rasterio`: https://rasterio.readthedocs.io
.. _`Xarray`: https://docs.xarray.dev/en/stable
.. _`NetCDF`: https://en.wikipedia.org/wiki/NetCDF
.. _`Zarr`: https://zarr.readthedocs.io/en/stable
.. _`GDAL raster driver short name`: https://gdal.org/drivers/raster/index.html
.. _`pyproj.CRS.from_user_input`: https://pyproj4.github.io/pyproj/stable/api/crs/coordinate_system.html#pyproj.crs.CoordinateSystem.from_user_input
