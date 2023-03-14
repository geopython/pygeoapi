.. _crs:

CRS support
===========

pygeoapi supports the complete specification: `OGC API - Features - Part 2: Coordinate Reference Systems by Reference corrigendum`_.
The specified CRS-related capabilities are available for all Feature data Providers.

Configuration
-------------

For details visit the :ref:`configuration` section for Feature Providers. At this moment only the 'URI' CRS notation format is supported.


* `crs` - list of CRSs supported
* `storage_crs` - CRS in which the data is stored (must be in `crs` list)
* `storage_crs_coordinate_epoch` - epoch of `storage_crs` for a dynamic coordinate reference system


These per-Provider configuration fields are all optional. Default for CRS-values is `http://www.opengis.net/def/crs/OGC/1.3/CRS84`, so "WGS84" with lon/lat axis ordering.
If the storage CRS of the spatial feature collection is a dynamic coordinate reference system,
`storage_crs_coordinate_epoch` configures the coordinate epoch of the coordinates.

There is also support for CRSs that support height like `http://www.opengis.net/def/crs/OGC/1.3/CRS84h`. In that case
bbox parameters (see below) may contain 6 coordinates.

Metadata
--------

The conformance class `http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs` is present as a `conformsTo` field
in the root landing page response.

The configured CRSs, or their defaults, `crs` and `storageCRS` and optionally `storageCrsCoordinateEpoch` will be present in the "Describe Collection" response.

Parameters
----------

The `items` query supports the following parameters:

* `crs` - the CRS in which Features coordinates should be returned, also for the 'get single item' request
* `bbox-crs` - the CRS of the `bbox` parameter (only for Providers that support the `bbox` parameter)

If any or both of these parameters are specified, their CRS-value should be from the advertised CRS-list in the Collection metadata (see above).

An HTTP Header named `Content-Crs` specifies the CRS for returned Feature-coordinates as
according to the "OGC API - Features - Part 2" standard. For example:

`Content-Crs: <http://www.opengis.net/def/crs/EPSG/0/3395>`.

Note that the values of these parameters may need to be URL-encoded.

Implementation
--------------

CRS and BBOX CRS support is implemented for all Feature Providers. Some details may help understanding (performance) implications.

BBOX CRS Parameter
^^^^^^^^^^^^^^^^^^

The `bbox-crs` parameter is handled at the common level of pygeoapi, thus transparent for Feature Providers.
Obviously the Provider should support `bbox`.
A transformation of the `bbox` parameter is performed
according to the `storage_crs` configuration. Then the (transformed) `bbox` is passed with the
other query parameters to the Provider instance.

CRS Parameter
^^^^^^^^^^^^^

When the value of the `crs` parameter differs from the Provider data Storage CRS, the response Feature coordinates
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
   "storageCRS": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


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

.. _`OGC API - Features - Part 2: Coordinate Reference Systems by Reference corrigendum`: https://docs.opengeospatial.org/is/18-058r1/18-058r1.html
