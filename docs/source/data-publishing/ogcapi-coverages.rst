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
   :header: Provider, range-subset, subset, bbox, datetime
   :align: left

   rasterio,✅,✅,✅,
   xarray,✅,✅,✅,✅


Below are specific connection examples based on supported providers.

Connection examples
-------------------

rasterio
^^^^^^^^

The `rasterio`_ provider plugin reads and extracts any data that rasterio is
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
   The rasterio provider ``format.name`` directive **requires** a valid
   `GDAL raster driver short name`_.

xarray
^^^^^^

The `xarray`_ provider plugin reads and extracts `NetCDF`_ and `Zarr`_ data.

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
* coverage access via native format (as defined in ``provider.format.name``)
  * http://localhost:5000/collections/foo/coverage?f=GRIB
* coverage access with comma-separated range-subset
  * http://localhost:5000/collections/foo/coverage?range-subset=1,3
* coverage access with subsetting
  * http://localhost:5000/collections/foo/coverage?subset=lat(10,20)&subset=long(10,20)

.. note::
   ``.../coverage`` queries which return an alternative representation to CoverageJSON (which prompt a download)
   will have the response filename matching the collection name and appropriate file extension (e.g. ``my-dataset.nc``)

.. _`OGC API - Coverages`: https://github.com/opengeospatial/ogcapi-coverages
.. _`rasterio`: https://rasterio.readthedocs.io
.. _`xarray`: https://xarray.pydata.org
.. _`NetCDF`: https://en.wikipedia.org/wiki/NetCDF
.. _`Zarr`: https://zarr.readthedocs.io/en/stable
.. _`GDAL raster driver short name`: https://gdal.org/drivers/raster/index.html
