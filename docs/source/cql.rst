.. _cql:

CQL support
===========

Providers
---------

As of now the available providers supported for CQL filtering are limited to :ref:`Elasticsearch <Elasticsearch>` &  :ref:`PostgreSQL <PostgreSQL>`..
 

Limitations
-----------

The Elasticsearch support to CQL is limited to `Simple CQL filter <https://portal.ogc.org/files/96288#cql-core>`_ and thus it allows to query with the
following predicates:

* comparison predicates
* spatial predicates
* temporal predicates

Formats
-------

At the moment Elasticsearch supports only the CQL dialect with the JSON encoding `CQL-JSON <https://portal.ogc.org/files/96288#simple-cql-JSON>`_.

PostGres supports both CQL dialects, `CQL-JSON <https://portal.ogc.org/files/96288#simple-cql-JSON>`_ & `CQL-TEXT <https://portal.ogc.org/files/96288#simple-cql-text>`_

Queries
^^^^^^^

PostGres provider utilizes `pygeofilter <https://github.com/geopython/pygeofilter>`_ allowing a range of filter expressions: 

* `Comparison predicates <https://portal.ogc.org/files/96288#simple-cql_comparison-predicates>`_
* `Spatial predicates <https://portal.ogc.org/files/96288#enhanced-spatial-operators>`_
* `Temporal predicates <https://portal.ogc.org/files/96288#simple-cql_temporal>

Using ElasticSearch the following type of queries are supported right now:

* ``between`` predicate query
* Logical ``and`` query with ``between`` and ``eq`` expression
* Spatial query with ``bbox``

Examples
^^^^^^^^

A ``between`` example for a specific property through an HTTP POST request:

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
