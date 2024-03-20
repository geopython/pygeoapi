.. _cql:

CQL support
===========

Providers
---------

As of now the available providers supported for CQL filtering are limited to :ref:`Elasticsearch <Elasticsearch>` and :ref:`PostgreSQL <PostgreSQL>`.
 
Limitations
-----------

Support of CQL is limited to `Simple CQL filter <https://portal.ogc.org/files/96288#cql-core>`_ and thus it allows to query with the
following predicates:

* comparison predicates
* spatial predicates
* temporal predicates

Formats
-------

At the moment Elasticsearch supports only the CQL dialect with the JSON encoding `CQL-JSON <https://portal.ogc.org/files/96288#simple-cql-JSON>`_.

PostgreSQL supports both CQL-JSON and CQL-text dialects, `CQL-JSON <https://portal.ogc.org/files/96288#simple-cql-JSON>`_ and `CQL-TEXT <https://portal.ogc.org/files/96288#simple-cql-text>`_

Queries
^^^^^^^

The PostgreSQL provider uses `pygeofilter <https://github.com/geopython/pygeofilter>`_ allowing a range of filter expressions, see examples for:

* `Comparison predicates <https://portal.ogc.org/files/96288#simple-cql_comparison-predicates>`_
* `Spatial predicates <https://portal.ogc.org/files/96288#enhanced-spatial-operators>`_
* `Temporal predicates <https://portal.ogc.org/files/96288#simple-cql_temporal>`_

Using Elasticsearch the following type of queries are supported right now:

* ``between`` predicate query
* Logical ``and`` query with ``between`` and ``eq`` expression
* Spatial query with ``bbox``

Note that when using a spatial operator in your filter expression, geometries are by default interpreted as being
in the OGC:CRS84 Coordinate Reference System. If you wish to provide geometries in other CRS, use the ``filter-crs``
query parameter with a suitable value.

Alternatively, a geometry's CRS may also be included using Extended Well-Known Text, in which case it will override
the value of ``filter-crs`` (if any) - this can be useful if your filtering expression is complex enough to
need multiple geometries expressed in different CRSs. The standard way of providing ``filter-crs`` as an additional
query parameter is preferable for most cases.

Examples
^^^^^^^^

A ``BETWEEN`` example for a specific property through an HTTP POST request:

.. code-block:: bash

  curl --location --request POST 'http://localhost:5000/collections/nhsl_hazard_threat_all_indicators_s_bc/items?f=json&limit=50&filter-lang=cql-json' \
  --header 'Content-Type: application/query-cql-json' \
  --data-raw '{
    "between": {
      "value": { "property": "properties.MHn_Intensity" },
      "lower": 0.59,
      "upper": 0.60
    }
  }'

Or 

.. code-block:: bash

  curl --location --request POST 'http://localhost:5000/collections/recentearthquakes/items?f=json&limit=10&filter-lang=cql-json' 
  --header 'Content-Type: application/query-cql-json' 
  --data-raw '{ 
    "between":{
      "value":{"property": "ml"},
      "lower":4,
      "upper":4.5
    }
  }'

The same ``BETWEEN`` query using HTTP GET request formatted as CQL text and URL encoded as below:

.. code-block:: bash

 curl "http://localhost:5000/collections/recentearthquakes/items?f=json&limit=10&filter=ml%20BETWEEN%204%20AND%204.5"

An ``EQUALS`` example for a specific property:

.. code-block:: bash

  curl --location --request POST 'http://localhost:5000/collections/recentearthquakes/items?f=json&limit=10&filter-lang=cql-json' 
  --header 'Content-Type: application/query-cql-json' 
  --data-raw '{
      "eq":[{"property": "user_entered"},"APBE"]
  }'

A ``CROSSES`` example via an HTTP GET request.  The CQL text is passed via the ``filter`` parameter.

.. code-block:: bash

  curl "http://localhost:5000/collections/hot_osm_waterways/items?f=json&filter=CROSSES(foo_geom,%20LINESTRING(28%20-2,%2030%20-4))"

A ``DWITHIN`` example via HTTP GET and using a custom CRS for the filter geometry:

.. code-block:: bash

  curl "http://localhost:5000/collections/beni/items?filter=DWITHIN(geometry,POINT(1392921%205145517),100,meters)&filter-crs=http://www.opengis.net/def/crs/EPSG/0/3857"


The same example, but this time providing a geometry in EWKT format:

.. code-block:: bash

  curl "http://localhost:5000/collections/beni/items?filter=DWITHIN(geometry,SRID=3857;POINT(1392921%205145517),100,meters)"




Note that the CQL text has been URL encoded. This is required in curl commands but when entering in a browser, plain text can be used e.g. ``CROSSES(foo_geom, LINESTRING(28 -2, 30 -4))``.
