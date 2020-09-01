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
   :header: Provider, rangeSubset, subset
   :align: left

   rasterio,✔️,✔️


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
             name: GRIB2
             mimetype: application/x-grib2

xarray
^^^^^^^^

The `xarray`_ provider plugin reads and extracts any data that xarray is
capable of handling (netCDF, Zarr).

.. code-block:: yaml

   providers:
       - type: coverage
         name: xarray
         data: tests/data/coads_sst.nc

Data access examples
--------------------

- list all collections
  - http://localhost:5000/collections
- overview of dataset
  - http://localhost:5000/collections/foo
- coverage rangetype
  - http://localhost:5000/collections/foo/coverage/rangetype
- coverage domainset
  - http://localhost:5000/collections/foo/coverage/domainset
- coverage access via CoverageJSON (default)
  - http://localhost:5000/collections/foo/coverage?f=json
- coverage access via native format (as defined in ``provider.format.name``)
  - http://localhost:5000/collections/foo/coverage?f=GRIB2
- coverage access with comma-separated rangeSubset
  - http://localhost:5000/collections/foo/coverage?rangeSubset=1,3
- coverage access with subsetting
  - http://localhost:5000/collections/foo/coverage?subset=lat(10,20)&subset=long(10,20)

.. _`OGC API - Coverages`: https://github.com/opengeospatial/ogc_api_coverages
.. _`rasterio`: https://rasterio.readthedocs.io
