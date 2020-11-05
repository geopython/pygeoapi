.. _cql-filter:

CQL Filter Implementation
=========================

pygeoapi is a Python server implementation of the OGC API suite of standards. OGC API standards define modular API building blocks to spatially enable Web API in a consistent way. This standard specifies the fundamental API building blocks for interacting with features. pygeoapi provides the capability for organizations to deploy a RESTful OGC API endpoint using OpenAPI, GeoJSON, and HTML. Project/code is structured to provide functionality via plugins where data can be fetched from any backend services like remote services or local files.

Querying is one of the fundamental operations performed on a collection of features. It is in order to obtain a subset of the data which contains feature instances that satisfy some filtering criteria. This project implements these enhanced filtering criteria in a request to a server. CQL is used to specify how resource instances in a source collection should be filtered to identify a result set. Typically, CQL is used here in query operations because it can be written in human readable format. So its the best query language that can be used to identify the subset of resources that should be included in a response document. Each resource instance in the source collection is evaluated using a filtering expression. The overall filter expression always evaluates to true or false. If the expression evaluates to true, the resource instance satisfies the expression and is marked as being in the result set. If the overall filter expression evaluates to false, the data instance is not in the result set.

This project is based on OGC API - Features - Part 3: Common Query Language document that defines the schema for a JSON document that exposes the set of properties or keys that may be used to construct CQL expressions for pygeoapi.


CQL Filter Predicates
---------------------
The following CQL predicates are implemented in pygeoapi to support filtering functionality on features:
Simple Condition Predicate, Combination Predicate, Not Condition Predicate, Between Predicate, Like Predicate, In Predicate, Null Predicate, BBox Predicate, Spatial Predicate and Temporal Predicate


CQL Filter Implementation for Data Providers 
--------------------------------------------
CQL implementation are provider for following data providers:

* CQL for CSV and GeoJSON data providers: Evaluation of the Abstract Syntax Tree to filter the feature collections supported by CSV and GeoJSON data providers. pycql library has implementation connection to databases using ORM, but in pygeoapi the data providers don't work with ORM. So the evaluation for all the CQL query operations are developed from scratch and by using efficient methodlogy. The evaluated output is the response from the API.

* CQL for SQLite data provider: Evaluation of the Abstract Syntax Tree to filter the feature collections supported by SQLite data provider. The AST of the CQL filter request is translated into SQL queries and then used as a request to the database. The evaluated output from the SQLite database is the response from the API.

* CQL for PostGreSQL data provider: Evaluation of the Abstract Syntax Tree to filter the feature collections supported by PostGreSQL data provider. Like SQLite quesries, the AST of the CQL filter request is translated into PostGreSQL queries by following the syntax of psycopg2 database adapter. The query is then used as a request to the database. The evaluated output from the PostGreSQL database is the response from the API.


Steps to generate and execute CQL endpoints
-------------------------------------------

pygeoapi is a Python server implementation of the OGC API suite of standards. The implementation of CQL is based on OGC API - Features - Part 3: Common Query Language document that defines the schema for a JSON document and exposes the set of properties or keys that may be used to construct CQL expressions for pygeoapi.

#. Install and run pygeoapi on localhost following the steps specified here


#. Go to OpenAPI documentation

.. image:: /_static/cql-filter/open_doc.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center

*pygeoapi currently supports two collections obs and lakes from CSV and GeoJSON data providers in OpenAPI Documentation*


#. Providing CQL query filter along with other query parameters. For the following parameters, the default value of limit is 10, startindex 0, CQL query language is in text, resulttype is results and output format is GeoJSON

.. image:: docs\source/_static/cql-filter/cql_query_parameters.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center
.. image:: docs\source/_static/cql-filter/cql_query_parameters2.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center
.. image:: docs\source/_static/cql-filter/cql_query_parameters3.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center

*The parameter values of any collection item can be changed to generate different API endpoint*

#. Click on Try it out to give the parameters value

.. image:: docs\source/_static/cql-filter/cql_query_parameter_value.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


#. Provide the CQL query parameter in text to filter the collection features Here assigning CQL filter as **WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371** and keeping the default values of all the other parameters.

.. image:: docs\source/_static/cql-filter/cql_insert_parameter.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


#. After filling the values of parameters (including CQL filter expression), click on execute. If the CQL expression is valid then an endpoint will be generated with Success code 200 and response body.

.. image:: docs\source/_static/cql-filter/cql_execute_endpoint.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


#. Furthermore the response body can be investigated by hitting the generated URL:

``http://localhost:5000/collections/lakes/items?f=json&filter-lang=cql-text&filter=WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371``


#. Since the output format was specified as GeoJSON the response from API is the following:

.. image:: docs\source/_static/cql-filter/cql_json_output.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


#. For the same CQL filter expression if the resulttype is chnaged to hits. The API response will have only the total count of features that satisfied the given fiter expression.

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=json&filter-lang=cql-text&resulttype=hits&filter=WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371``

**Response:**

.. image:: docs\source/_static/cql-filter/cql_json_output2.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


#. To overlay the response from API on a map, we can change the output format of the endpoint from JSON to HTML

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&filter=WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371``

**Response:**

.. image:: docs\source/_static/cql-filter/cql_html_output.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


#. If any invalid CQL filter expression is provided then the API raises an exception and the response is as follows:

**Requested API:**

``http://localhost:5000/collections/obs/items?f=json&filter-lang=cql-text&filter=INTERSECTION(geometry,POINT (-75 45))``

**Response:**

.. image:: docs\source/_static/cql-filter/cql_invalid_output.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&filter=id IN ['A','B']``

**Response:**

.. image:: docs\source/_static/cql-filter/cql_invalid_output2.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&filter=name@obs``

**Response:**

.. image:: docs\source/_static/cql-filter/cql_invalid_output3.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center


**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&filter=name LIKE 2``

**Response:**

.. image:: /_static/cql-filter/cql_invalid_output4.png
   :scale: 70%
   :alt: generate and execute CQL endpoints
   :align: center



.. _cql-filter