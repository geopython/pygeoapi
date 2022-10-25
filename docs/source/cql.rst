.. _cql:

CQL support
===========

Providers
---------

As of now the available providers supported for CQL filtering are limited to :ref:`Elasticsearch <Elasticsearch>` & :ref:`PostgreSQL <PostgreSQL>`.
 
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

PostgreSQL supports both CQL-JSON and CQL-text dialects, `CQL-JSON <https://portal.ogc.org/files/96288#simple-cql-JSON>`_ & `CQL-TEXT <https://portal.ogc.org/files/96288#simple-cql-text>`_

Queries
^^^^^^^

The PostgreSQL provider uses `pygeofilter <https://github.com/geopython/pygeofilter>`_ allowing a range of filter expressions, see examples for:

* `Comparison predicates <https://portal.ogc.org/files/96288#simple-cql_comparison-predicates>`_
* `Spatial predicates <https://portal.ogc.org/files/96288#enhanced-spatial-operators>`_
* `Temporal predicates <https://portal.ogc.org/files/96288#simple-cql_temporal>

Using ElasticSearch the following type of queries are supported right now:

* ``between`` predicate query
* Logical ``and`` query with ``between`` and ``eq`` expression
* Spatial query with ``bbox``

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

  curl --location --request POST 'https://ogcapi.bgs.ac.uk/collections/recentearthquakes/items?f=json&limit=10&filter-lang=cql-json' 
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

 curl "https://ogcapi.bgs.ac.uk/collections/recentearthquakes/items?f=json&limit=10&filter=ml%20BETWEEN%204%20AND%204.5"

An ``EQUALS`` example for a specific property:

.. code-block:: bash
  curl --location --request POST 'https://ogcapi.bgs.ac.uk/collections/recentearthquakes/items?f=json&limit=10&filter-lang=cql-json' 
  --header 'Content-Type: application/query-cql-json' 
  --data-raw '{
      "eq":[{"property": "user_entered"},"APBE"]
  }'

A ``CROSSES`` example via an HTTP GET request.  The CQL text is passed via the ``filter`` parameter.

.. code-block:: bash

  curl "http://localhost:5000/collections/hot_osm_waterways/items?f=json&filter=CROSSES(foo_geom,%20LINESTRING(28%20-2,%2030%20-4))"

Note the the CQL text has been URL encoded here.
This is required in CURL commands but when entering in a browser, plain text can be used e.g. "CROSSES(foo_geom, LINESTRING(28 -2, 30 -4))".