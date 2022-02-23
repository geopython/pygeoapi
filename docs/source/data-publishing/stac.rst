.. _stac:

Publishing files to a SpatioTemporal Asset Catalog
**************************************************

The `SpatioTemporal Asset Catalog (STAC)`_ family of specifications aim to standardize
the way geospatial asset metadata is structured and queried. A "spatiotemporal asset"
is any file that represents information about the Earth at a certain place and time.
The original focus was on scenes of satellite imagery, but the specifications now cover
a broad variety of uses, including sources such as aircraft and drone and data such as
hyperspectral optical, synthetic aperture radar (SAR), video, point clouds, lidar, digital
elevation models (DEM), vector, machine learning labels, and composites like NDVI and
mosaics. STAC is intentionally designed with a minimal core and flexible extension mechanism
to support a broad set of use cases. This specification has matured over the past several
years, and is used in numerous production deployments.

pygeoapi has two built-in providers to browse STAC catalogs: `FileSystem Provider`_ and
`Hateoas Provider`_.

Hateoas Provider
================

HATEOAS (Hypermedia as the Engine of Application State) is a way of implementing a REST
application that allows the client to dynamically navigate to the appropriate resources
by browsing hypermedia links. This type of navigation is similar to WEB navigation
and requires a very precise data structure that must be respected to allow the HATEOAS
Provider to behave correctly.

There are three component specifications (Catalog, Collection, Item) that together make
up the core SpatioTemporal Asset Catalog specification. An Item represents a single
spatiotemporal asset as GeoJSON. The Catalog specification provides structural elements,
to group Items and Collections. Collections are catalogs, that add more required metadata
and describe a group of related Items.

The full catalog structure of links down to sub-catalogs and Items, and their links back to
their parents and roots, must be done with **relative** URL's for the HATEOAS Provider work
correctly. The structural *rel* types include *root*, *parent*, *child*, *item*, and
*collection*. Assets links must be **absolute** URL's. Other links can be absolute, especially
if they describe a resource that makes less sense in the catalog, like derived_from or even
license (it can be nice to include the license in the catalog, but some licenses live at a
canonical online location which makes more sense to refer to directly). This enables the
full catalog (excluding the assets) to be downloaded or copied to another location and to
still be valid. This also implies no self link, as that link must be absolute.

So, the following rules must be respected:

1. Root documents (Catalogs / Collections) must be at the root of a directory tree containing the static catalog.

2. Catalogs must be named catalog.json and Collections must be named collection.json.

3. Sub-Catalogs or sub-Collections must be stored in subdirectories of their parent (and only 1 subdirectory deeper than a document's parent, e.g. .../sample/sub1/catalog.json).

4. Limit the number of Items in a Catalog or Collection, grouping / partitioning as relevant to the dataset.

5. Use structural elements (Catalog and Collection) consistently across each 'level' of your hierarchy. For example, if levels 2 and 4 of the hierarchy only contain Collections, don't add a Catalog at levels 2 and 4.

6. Items must be named <*id*>.json.

7. Items must be stored in subdirectories (1 level deeper) of their parent Catalog or Collection. The subdirectory must have the same name (<*id*>) as the Item without the *.json* extension. This means that each Item are contained in a unique subdirectory.

8. The links to the actual assets must be an absolute URL.

-------------

File examples
-------------

**Structure of the catalog.json file**

.. code-block:: json

  {
      "id": "STAC-Catalog",
      "stac_version": "1.0.0",
      "description": "A description of the STAC Catalog",
      "links": [
          {
              "rel": "root",
              "href": "./catalog.json",
              "type": "application/json"
          },
          {
              "rel": "child",
              "href": "./eo4ce/catalog.json",
              "type": "application/json"
          },
          ...
          {
              "rel": "child",
              "href": "./dem/catalog.json",
              "type": "application/json"
          }
      ],
      "stac_extensions": [],
      "title": "STAC Catalog"
  }

The code above shows the root catalog. The sub-catalogs have an additional ``rel`` entry pointing to the parent.

.. code-block:: json

  {
      "id": "dem",
      "stac_version": "1.0.0",
      "description": "Digital Elevation Data",
      "links": [
          {
              "rel": "root",
              "href": "../catalog.json",
              "type": "application/json"
          },
          {
              "rel": "child",
              "href": "./hrdsm/collection.json",
              "type": "application/json"
          },
          {
              "rel": "parent",
              "href": "../catalog.json",
              "type": "application/json"
          }
      ],
      "stac_extensions": [],
      "title": "DEM"
  }

-------------------------------------

**Structure of the collection.json file**

Collections are similar to Catalogs with extra fields.

.. code-block:: json

  {
      "id": "hrdsm",
      "stac_version": "1.0.0",
      "description": "High Resolution Digital Surface Model",
      "links": [
          {
              "rel": "root",
              "href": "../../catalog.json",
              "type": "application/json"
          },
          {
              "rel": "item",
              "href": "./arcticdem-frontiere-0/arcticdem-frontiere-0.json",
              "type": "application/json"
          },
          ...
          {
              "rel": "item",
              "href": "./arcticdem-frontiere-9/arcticdem-frontiere-9.json",
              "type": "application/json"
          },
          {
              "rel": "parent",
              "href": "../catalog.json",
              "type": "application/json"
          }
      ],
      "stac_extensions": [],
      "extent": {
          "spatial": {
              "bbox": [
                  [
                      -142.76516601842533,
                      59.65274347822059,
                      -138.41658819177135,
                      69.81052152420365
                  ]
              ]
          },
          "temporal": {
              "interval": [
                  [
                      "2014-09-03T14:00:00Z",
                      "2020-09-28T15:49:00.559166Z"
                  ]
              ]
          }
      },
      "license": "proprietary"
  }

-------------------------------------

**Structure of the Item <id>.json file**

The example below shows the content of a file named *arcticdem-frontiere-0.json*.

.. code-block:: json

  {
      "type": "Feature",
      "stac_version": "1.0.0",
      "id": "arcticdem-frontiere-0",
      "properties": {
          "layer:ids": [
              "dem-hrdsm"
          ],
          "collection": "hrdsm",
          "datetime": "2020-09-28T15:48:56.483794Z"
      },
      "geometry": {
          "type": "Polygon",
          "coordinates": [
              [
                  [
                      -140.27389595735178,
                      59.65274347822059
                  ],
                  [
                      -138.41658819177135,
                      59.65274347822059
                  ],
                  [
                      -138.41658819177135,
                      60.579416456816496
                  ],
                  [
                      -140.27389595735178,
                      60.579416456816496
                  ],
                  [
                      -140.27389595735178,
                      59.65274347822059
                  ]
              ]
          ]
      },
      "links": [
          {
              "rel": "root",
              "href": "../../../catalog.json",
              "type": "application/json"
          },
          {
              "rel": "collection",
              "href": "../collection.json",
              "type": "application/json"
          },
          {
              "rel": "parent",
              "href": "../collection.json",
              "type": "application/json"
          }
      ],
      "assets": {
          "image": {
              "href": "http://absolute/path/to/the/ressource/arcticdem-frontiere-0.tif",
              "type": "image/tiff; application=geotiff; profile=cloud-optimized",
              "roles": []
          }
      },
      "bbox": [
          -140.27389595735178,
          59.65274347822059,
          -138.41658819177135,
          60.579416456816496
      ],
      "stac_extensions": [],
      "collection": "hrdsm"
  }

---------------------

HATEOAS Configuration
---------------------

Configuring HATEOAS STAC Provider in pygeoapi is done by simply pointing the ``data`` provider property
to the local directory or remote URL and specifying the root file name (catalog.json or collection.json) in the file_types property:

Connection examples
-------------------

.. code-block:: yaml

   my-remote-stac-resource:
       type: stac-collection
       ...
       providers:
           - type: stac
             name: Hateoas
             data: https://datacube-dev-data-public.s3.ca-central-1.amazonaws.com/catalog/water
             file_types: catalog.json

   my-local-stac-resource:
       type: stac-collection
       ...
       providers:
           - type: stac
             name: Hateoas
             data: tests/stac
             file_types: catalog.json

-------------------

FileSystem Provider
===================

The FileSystem Provider implements STAC as a geospatial file browser through the server's file system,
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
