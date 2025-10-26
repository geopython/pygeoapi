.. _crs:

CRS support
===========

pygeoapi supports multiple Coordinate Reference Systems (CRS). 
This enables the import and export of any data according to dedicated projections.
A "projection" is specified with a CRS identifier.
In particular CRS support allows for the following:

* to specify the CRS in which the data is stored, in pygeoapi the `storage_crs` config option
* to specify the list of valid CRS representations, in pygeoapi the `crs` config option
* to publish these in the collection metadata
* the `bbox-crs=` query parameter to indicate that the `bbox=` parameter is encoded in that CRS
* the `crs=` query parameter for a collection or collection item
* the HTTP response header `Content-Crs` denotes the CRS of the Feature(s) in the data returned

Although GeoJSON mandates WGS84 in longitude, latitude order, the client and server may still agree on other CRSs.


Background
----------

pygeoapi implements the `OGC API - Features - Part 2: Coordinate Reference Systems by Reference`_ specification.

Under the hood, pygeoapi uses the `pyproj`_ Python package.

.. note::

   For more information on implementing CRS on custom plugins, see `Implementation`_.

CRS support exists for the following OGC APIs:

.. csv-table::
   :header: OGC API, bbox-crs, filter-crs, crs
   :align: left

   :ref:`OGC API - Features<ogcapi-features>`,✅,✅,✅
   :ref:`OGC API - Maps<ogcapi-maps>`,✅,❌,❌
   :ref:`OGC API - Coverages<ogcapi-coverages>`,✅,❌,❌

Configuration
-------------

The CRS of a collection is defined in the provider block of your resource.
The configuration controls how the `crs` related query parameters behave.


* ``crs`` - list of CRSs supported
* ``storage_crs`` - CRS in which the data is stored (must be in `crs` list)
* ``storage_crs_coordinate_epoch`` - epoch of `storage_crs` for a dynamic coordinate reference system
* ``always_xy`` - CRS should ignore authority on axis order, disobeying `ISO-19111`_ (default: false) 

.. note::
    bbox-crs and filter-crs are used to convert the request geometry to the configured ``storage_crs``.
    An error will be returned for any interaction with CRS not included in the configured ``crs`` list.

The per-Provider configuration fields are all optional,
with the following as default configuration:

.. code-block:: yaml

    crs:
        - http://www.opengis.net/def/crs/OGC/1.3/CRS84
        - http://www.opengis.net/def/crs/OGC/1.3/CRS84h
    storage_crs: http://www.opengis.net/def/crs/OGC/1.3/CRS84

.. note::
    Configuration is done with URI formats like http://www.opengis.net/def/crs/OGC/1.3/CRS84. 
    Both `URI` and `URN` CRS notation format are supported.
    The `EPSG:` format like EPSG:4326 is outside the scope of the OGC standard.


Metadata
--------

The conformance class http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs is
present as a `conformsTo` field in the root landing page response.

The configured CRSs, or their defaults, `crs` and `storageCrs` and optionally `storageCrsCoordinateEpoch` will be present in the "Describe Collection" response.

.. note::
    If the storage CRS of the spatial feature collection is a dynamic coordinate reference system,
    `storage_crs_coordinate_epoch` configures the coordinate epoch of the coordinates.

.. note::
    There is also support for CRSs that support height like `http://www.opengis.net/def/crs/OGC/1.3/CRS84h`. In that case
    bbox parameters (see below) may contain 6 coordinates.

Parameters
----------

The `items` query supports the following parameters:

* ``crs`` - the CRS in which Features coordinates should be returned, also for the 'get single item' request
* ``bbox-crs`` - the CRS of the `bbox` parameter (for Providers that support the `bbox` parameter)
* ``filter-crs`` - the CRS of the CQL filter expression (for Providers that support `CQL` filters)

If any or both of these parameters are specified, their CRS-value should be from the advertised CRS-list in the Collection metadata (see above).

An HTTP Header named `Content-Crs` specifies the CRS for returned Feature-coordinates as
according to the "OGC API - Features - Part 2" standard. For example:

`Content-Crs: <http://www.opengis.net/def/crs/EPSG/0/3395>`.

Note that the values of these parameters may need to be URL-encoded.

Implementation
--------------

CRS and BBOX CRS support is implemented for all Feature Providers.
Some details may help understanding (performance) implications.

bbox-crs Parameter
^^^^^^^^^^^^^^^^^^

The ``bbox-crs`` parameter is handled at the common level of pygeoapi.
A transformation of the request `bbox` parameter is performed
according to the `storage_crs` configuration. Then the (transformed) `bbox` is passed with the
other query parameters to the Provider instance.

filter-crs Parameter
^^^^^^^^^^^^^^^^^^^^

The ``filter-crs`` parameter is handled at the common level of pygeoapi.
A transformation of the request `CQL` filter is performed
according to the `storage_crs` configuration. Then the (transformed) `filter` is passed with the
other query parameters to the Provider instance.

crs Parameter
^^^^^^^^^^^^^

When the value of the ``crs`` parameter differs from the Provider data Storage CRS, the response Feature coordinates
need to be transformed to that CRS. As some Feature Providers like PostgreSQL or OGR may support native
coordinate transformation, pygeoapi delegates transformation to those Providers, passing the `crs` with the other query parameters.

Feature Providers, like CSV for example, that do not (yet) support coordinate transformation provide a 'flag'
that triggers pygeoapi to perform the transformation on the Provider response data.
Details: this is effected through a Python Decorator `@crs_transform` on the Provider functions `query()` and  `get()`.
By removing that flag, Providers may later move transformation to their internal implementation.


Examples
--------

Suppose an addresses collection with the following CRS support in its collection metadata:

.. code-block:: bash


   curl 'http://localhost:5000/collections/dutch_addresses_4326?f=json'

    .
    .

   "crs": [
    "http://www.opengis.net/def/crs/EPSG/0/4326",
    "http://www.opengis.net/def/crs/EPSG/0/3857",
    "http://www.opengis.net/def/crs/EPSG/0/28992",
    "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
   ],
   "storageCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


This allows a `bbox-crs` query using Dutch "RD" coordinates with CRS `http://www.opengis.net/def/crs/EPSG/0/28992` to retrieve
for example a single address. Note that the URIs are URL-encoded,
This is sometimes required in `curl` commands but when entering in a browser, plain text can be used.
Though `curl` may also understand non-encoded URLs when using single quotes around the complete URL.

.. code-block:: bash

  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&bbox=177430,459268,177440,459278'
  # or plain URL
  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&bbox-crs=http://www.opengis.net/def/crs/EPSG/0/28992&bbox=177430,459268,177440,459278'

  # response fragment
  {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    5.714846709450305,
                    52.12122746454743
                ]
            },
            "properties": {
                "straatnaam": "Willinkhuizersteeg",
                "huisnummer": "2",
                "huisletter": "C",
                "woonplaats": "Wekerom",
                "postcode": "6733EB",
                "toevoeging": null
            },
            "id": "inspireadressen.1742212"
        }
    ],
    "links": [
    .
    .

You can also use a WGS84 equivalent with lat/lon axis order as in CRS `http://www.opengis.net/def/crs/EPSG/0/4326`.

.. code-block:: bash

  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F4326&bbox=52.12122,5.71484,52.12123,5.71486'

  # response fragment
  {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    5.714846709450305,
                    52.12122746454743
                ]
            },
            "properties": {
                "straatnaam": "Willinkhuizersteeg",
                "huisnummer": "2",
                "huisletter": "C",
                "woonplaats": "Wekerom",
                "postcode": "6733EB",
                "toevoeging": null
            },
            "id": "inspireadressen.1742212"
        }
    ],
    "links": [
    .
    .

Using the `crs` parameter you can retrieve the data within the bbox in a different CRS like
`http://www.opengis.net/def/crs/EPSG/0/28992`. The `bbox` is assumed to specified in the Storage CRS `http://www.opengis.net/def/crs/OGC/1.3/CRS84`.

.. code-block:: bash

  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&bbox=5.71484,52.12122,5.71486,52.12123'
  # or plain URL
  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&crs=http://www.opengis.net/def/crs/EPSG/0/28992&bbox=5.71484,52.12122,5.71486,52.12123'

  # response fragment
  {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    177439.0002001376,
                    459273.9995615507
                ]
            },
            "properties": {
                "straatnaam": "Willinkhuizersteeg",
                "huisnummer": "2",
                "huisletter": "C",
                "woonplaats": "Wekerom",
                "postcode": "6733EB",
                "toevoeging": null
            },
            "id": "inspireadressen.1742212"
        }
    ],
    "links": [
    .
    .


Or you may specify both `crs` and `bbox-crs` and thus `bbox` in that CRS `http://www.opengis.net/def/crs/EPSG/0/28992`.

.. code-block:: bash

  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&bbox-crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&bbox=177430,459268,177440,459278'
  # or plain URL
  curl 'http://localhost:5000/collections/dutch_addresses_4326/items?f=json&crs=http://www.opengis.net/def/crs/EPSG/0/28992&bbox-crs=http://www.opengis.net/def/crs/EPSG/0/28992&bbox=177430,459268,177440,459278'

  # response fragment
  {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    177439.0002001376,
                    459273.9995615507
                ]
            },
            "properties": {
                "straatnaam": "Willinkhuizersteeg",
                "huisnummer": "2",
                "huisletter": "C",
                "woonplaats": "Wekerom",
                "postcode": "6733EB",
                "toevoeging": null
            },
            "id": "inspireadressen.1742212"
        }
    ],
    "links": [
    .
    .

.. _`ISO-19111`: https://docs.ogc.org/as/18-005r5/18-005r5.html
.. _`OGC API - Features - Part 2: Coordinate Reference Systems by Reference`: https://docs.ogc.org/is/18-058r1/18-058r1.html
.. _`pyproj`: https://pyproj4.github.io/pyproj