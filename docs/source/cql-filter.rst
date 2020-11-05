.. _cql-filter:

CQL Filter Implementation
=========================

pygeoapi is a Python server implementation of the OGC API suite of standards. OGC API standards define modular API building blocks to spatially enable Web API in a consistent way. This standard specifies the fundamental API building blocks for interacting with features. pygeoapi provides the capability for organizations to deploy a RESTful OGC API endpoint using OpenAPI, GeoJSON, and HTML. Project/code is structured to provide functionality via plugins where data can be fetched from any backend services like remote services or local files.

Querying is one of the fundamental operations performed on a collection of features. It is in order to obtain a subset of the data which contains feature instances that satisfy some filtering criteria. This project implements these enhanced filtering criteria in a request to a server. CQL is used to specify how resource instances in a source collection should be filtered to identify a result set. Typically, CQL is used here in query operations because it can be written in human readable format. So its the best query language that can be used to identify the subset of resources that should be included in a response document. Each resource instance in the source collection is evaluated using a filtering expression. The overall filter expression always evaluates to true or false. If the expression evaluates to true, the resource instance satisfies the expression and is marked as being in the result set. If the overall filter expression evaluates to false, the data instance is not in the result set.

This project is based on `OGC API - Features - Part 3: Common Query Language <http://docs.opengeospatial.org/DRAFTS/19-079.html>`_ document that defines the schema for a JSON document that exposes the set of properties or keys that may be used to construct CQL expressions for pygeoapi.


CQL Filter Predicates
---------------------

The following CQL predicates are implemented in pygeoapi to support filtering functionality on features:

*Simple Condition Predicate, Combination Predicate, Not Condition Predicate, Between Predicate, Like Predicate, In Predicate, Null Predicate, BBox Predicate, Spatial Predicate and Temporal Predicate*


CQL Filter Implementation for Data Providers 
--------------------------------------------

CQL implementation are provider for following data providers:

* **CQL for CSV and GeoJSON data providers:** Evaluation of the Abstract Syntax Tree to filter the feature collections supported by CSV and GeoJSON data providers. pycql library has implementation connection to databases using ORM, but in pygeoapi the data providers don't work with ORM. So the evaluation for all the CQL query operations are developed from scratch and by using efficient methodlogy. The evaluated output is the response from the API.

* **CQL for SQLite data provider:** Evaluation of the Abstract Syntax Tree to filter the feature collections supported by SQLite data provider. The AST of the CQL filter request is translated into SQL queries and then used as a request to the database. The evaluated output from the SQLite database is the response from the API.

* **CQL for PostGreSQL data provider:** Evaluation of the Abstract Syntax Tree to filter the feature collections supported by PostGreSQL data provider. Like SQLite quesries, the AST of the CQL filter request is translated into PostGreSQL queries by following the syntax of psycopg2 database adapter. The query is then used as a request to the database. The evaluated output from the PostGreSQL database is the response from the API.


Steps to generate and execute CQL endpoints
-------------------------------------------

1. Install and run pygeoapi on localhost following the steps specified here


2. Go to OpenAPI documentation

.. image:: /_static/cql-filter/cql_open_doc.png
   :alt: generate and execute CQL endpoints
   :align: center

*pygeoapi currently supports two collections obs and lakes from CSV and GeoJSON data providers in OpenAPI Documentation*


3. Providing CQL query filter along with other query parameters. For the following parameters, the default value of limit is 10, startindex 0, CQL query language is in text, resulttype is results and output format is GeoJSON

.. image:: /_static/cql-filter/cql_query_parameters.png
   :alt: generate and execute CQL endpoints
   :align: center
.. image:: /_static/cql-filter/cql_query_parameters2.png
   :alt: generate and execute CQL endpoints
   :align: center
.. image:: /_static/cql-filter/cql_query_parameters3.png
   :alt: generate and execute CQL endpoints
   :align: center

*The parameter values of any collection item can be changed to generate different API endpoint*

4. Click on Try it out to give the parameters value

.. image:: /_static/cql-filter/cql_query_parameter_value.png
   :alt: generate and execute CQL endpoints
   :align: center
   

5. Provide the CQL query parameter in text to filter the collection features Here assigning CQL filter as **WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371** and keeping the default values of all the other parameters.

.. image:: /_static/cql-filter/cql_insert_parameter.png
   :alt: generate and execute CQL endpoints
   :align: center


6. After filling the values of parameters (including CQL filter expression), click on execute. If the CQL expression is valid then an endpoint will be generated with Success code 200 and response body.

.. image:: /_static/cql-filter/cql_execute_endpoint.png
   :alt: generate and execute CQL endpoints
   :align: center


7. Furthermore the response body can be investigated by hitting the generated URL:

``http://localhost:5000/collections/lakes/items?f=json&filter-lang=cql-text&`` ``filter=WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371``


8. Since the output format was specified as GeoJSON the response from API is the following:

.. image:: /_static/cql-filter/cql_json_output.png
   :alt: generate and execute CQL endpoints
   :align: center


9. For the same CQL filter expression if the resulttype is chnaged to hits. The API response will have only the total count of features that satisfied the given fiter expression.

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=json&filter-lang=cql-text&resulttype=hits&`` ``filter=WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371``

**Response:**

.. image:: /_static/cql-filter/cql_json_output2.png
   :alt: generate and execute CQL endpoints
   :align: center


* To overlay the response from API on a map, we can change the output format of the endpoint from JSON to HTML

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&`` ``filter=WITHIN(geometry, POLYGON((-80.0 -80.0,-80.0 50,80.0 50,-80.0 -80.0))) AND id<>371``

**Response:**

.. image:: /_static/cql-filter/cql_html_output.png
   :alt: generate and execute CQL endpoints
   :align: center


* If any invalid CQL filter expression is provided then the API raises an exception and the response is as follows:

**Requested API:**

``http://localhost:5000/collections/obs/items?f=json&filter-lang=cql-text&`` ``filter=INTERSECTION(geometry,POINT (-75 45))``

**Response:**

.. image:: /_static/cql-filter/cql_invalid_output.png
   :alt: generate and execute CQL endpoints
   :align: center


**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&filter=id IN ['A','B']``

**Response:**

.. image:: /_static/cql-filter/cql_invalid_output2.png
   :alt: generate and execute CQL endpoints
   :align: center


**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&
filter=name@obs``

**Response:**

.. image:: /_static/cql-filter/cql_invalid_output3.png
   :alt: generate and execute CQL endpoints
   :align: center


**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&
filter=name LIKE 2``

**Response:**

.. image:: /_static/cql-filter/cql_invalid_output4.png
   :alt: generate and execute CQL endpoints
   :align: center


Examples of CQL query filter
-----------------------------
Following are few examples of CQL query filter implemented on pygeoapi data providers-

Getting started
^^^^^^^^^^^^^^^

The collections used for the project demonstration here are observation and lake features from CSV and GeoJSON data providers respectively.The attribute table for observation and lake features are as follows:

**obs.csv**

.. image:: /_static/cql-filter/cql_obs.png
   :alt: example of cql query filter
   :align: center

**lakes.geojson**

.. image:: /_static/cql-filter/cql_lakes.png
   :alt: example of cql query filter
   :align: center
.. image:: /_static/cql-filter/cql_lakes2.png
   :alt: example of cql query filter
   :align: center

*For the following API requests the default value of limit is 10, startindex is 0 and CQL query language is text*

Simple comparisons
^^^^^^^^^^^^^^^^^^

Let’s get started with the simple examples. In CQL comparisons are expressed using plain text.

* The filter **stn_id >= 35** will filter the observations that have **stn_id** value greater than or equals to 35:

**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter=stn_id>=35&filter-lang=cql-text``

**Response:**

.. image:: /_static/cql-filter/example1.png
   :alt: example of cql query filter
   :align: center

* The filter **stn_id <= 604** will select observations that have **stn_id** less than or equals than 604:

**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter=stn_id<=604&filter-lang=cql-text``

**Response:**

.. image:: /_static/cql-filter/example2.png
   :alt: example of cql query filter
   :align: center

* If we want to look for Lake Baikal on the map, then the filter **name='Lake Baikal'** will fetch its details and display its location on the world's map.
The requested API to GeoJSON Data provider for filtering Lake Baikal should be:

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&filter=name='Lake Baikal'``

**Response:**

.. image:: /_static/cql-filter/example3.png
   :alt: example of cql query filter
   :align: center

* To filter lakes whose **id** is not equals to 0, than the filter id<>0 will response with all the lake features except the one with **id=0**.

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=100&filter-lang=cql-text&filter=id<>0``

**Response:**

.. image:: /_static/cql-filter/example4.png
   :alt: example of cql query filter
   :align: center

* If there is a requirement to fetch only 5 lakes starting from index 10 and having filter as **id>10**. 

*pygeoapi supports limit and startindex request parameters, so an API call is possible with CQL query filter along with other query parameters.*

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=5&startindex=10&filter-lang=cql-text&filter=id>10``

**Response:**

.. image:: /_static/cql-filter/example5.png
   :alt: example of cql query filter
   :align: center

Due to the implementation of CQL extension on pygeoapi, all the simple comparison operations are now supported on any number of feature collections.

*The common comparison operators are: <, >, <=, >=, =, <>*

* To select a range of values the BETWEEN operator can be used like **id BETWEEN 20 AND 25**

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=100&filter-lang=cql-text&filter=id BETWEEN 20 AND 25``

**Response:**

.. image:: /_static/cql-filter/example6.png
   :alt: example of cql query filter
   :align: center

* If needed to filter out lake features with no admin then **admin IS NULL** will response with required lakes.

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=1000&filter-lang=cql-text&filter=admin IS NULL``

**Response:**

.. image:: /_static/cql-filter/example7.png
   :alt: example of cql query filter
   :align: center


String comparisons
^^^^^^^^^^^^^^^^^^

* In one of the above example we have already seen that comparison operators also support text values. For instance, to select only Lake Baikal, the filter was name='Lake Baikal'. But more general text/string comparisons can be made using the LIKE operator. name **NOT LIKE '%Lake%'** will extract all lakes that does not have 'Lake' anywhere in their name.

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&&filter-lang=cql-textfilter=name NOT LIKE '%Lake%'``

**Response:**

.. image:: /_static/cql-filter/example8.png
   :alt: example of cql query filter
   :align: center

* Suppose we want to find all lakes whose name contains an 'great', regardless of letter case. We cannot use LIKE operator here as it is case sensitive. ILIKE operator can be used to ignore letter casing: **name ILIKE '%great%'**

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&filter=name ILIKE "%great%"``

**Response:**

.. image:: /_static/cql-filter/example9.png
   :alt: example of cql query filter
   :align: center

*The comparison on strings can be performed with either of the following: LIKE, NOT LIKE, ILIKE , NOT LIKE*

The CQL extension on pygeoapi supports all the above specified formats for comparing strings.


List comparisons
^^^^^^^^^^^^^^^^

* If we want to extract only specific lakes whose **name** is in a given list, then we can use the IN operator specifying an attribute name as in **name IN ('Lake Baikal','Lake Huron','Lake Onega','Lake Victoria')**

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=1000&filter-lang=cql-text&`` ``filter=name IN ('Lake Baikal','Lake Huron','Lake Onega','Lake Victoria')``

**Response:**

.. image:: /_static/cql-filter/example10.png
   :alt: example of cql query filter
   :align: center

* If the requirement is to get all the lakes from the collection except the ones specified in the list then **name NOT IN ('Lake Baikal','Lake Huron','Lake Onega','Lake Victoria')** will serve our purpose.

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=1000&filter-lang=cql-text&`` ``filter=name NOT IN ('Lake Baikal','Lake Huron','Lake Onega','Lake Victoria')``

**Response:**

.. image:: /_static/cql-filter/example11_a.png
   :alt: example of cql query filter
   :align: center
.. image:: /_static/cql-filter/example11_b.png
   :alt: example of cql query filter
   :align: center
.. image:: /_static/cql-filter/example11_c.png
   :alt: example of cql query filter
   :align: center


Combination filters
^^^^^^^^^^^^^^^^^^^

The CQL extension on pygeoapi is eligible to support filters that are a combination of more than one simple query filters.

*The logical operators are: AND, OR*

* To extract all the lakes whose id is less than 5 and name starts with 'Lake' then the combination of two filters can be formed as **id<5 AND name LIKE "Lake%"**

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=100&filter-lang=cql-text&`` ``filter=id<5 AND name LIKE "Lake%"``

**Response:**

.. image:: /_static/cql-filter/example12.png
   :alt: example of cql query filter
   :align: center

* Furthermore, if a lake has an admin and its id is greater than 5 or its name contains 'lake' string irrespective of letter case, then the complex CQL filter query will be like: **admin IS NOT NULL AND id>5 OR name ILIKE "%lake%**

**Requested API:**

``http://localhost:5000/collections/lakes/items?limit=100&filter-lang=cql-text&`` ``filter=admin IS NOT NULL AND id>5 OR name ILIKE "%lake%"``

**Response:**

.. image:: /_static/cql-filter/example13.png
   :alt: example of cql query filter
   :align: center


Spatial filters
^^^^^^^^^^^^^^^

* CQL provides a full set of geometric filter capabilities. Say, for example, if we want to display only the lakes that intersect the (-90,40,-60,45) bounding box. The filter will be **BBOX(geometry, -90, 40, -60, 45)**

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&`` ``filter=BBOX(geometry, -90, 40, -60, 45)``

**Response:**

.. image:: /_static/cql-filter/example14.png
   :alt: example of cql query filter
   :align: center

* Conversely, we can select the states that do not intersect the bounding box with the filter: **DISJOINT(the_geom, POLYGON((-90 40, -90 45, -60 45, -60 40, -90 40)))**

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&`` ``filter=DISJOINT(the_geom, POLYGON((-90 40, -90 45, -60 45, -60 40, -90 40))``

**Response:**

.. image:: /_static/cql-filter/example15.png
   :alt: example of cql query filter
   :align: center

* If needed to extract the information of a lake that contains a particular geometry. Then **CONTAINS(geometry, POLYGON((108.58 54.19, 108.37 54.04, 108.48 53.94, 108.77 54.01, 108.77 54.11, 108.58 54.19)))** will return the feature that contains a polygon of specified coordinates.

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&`` ``filter=CONTAINS(geometry, POLYGON((108.58 54.19, 108.37 54.04, 108.48 53.94, 108.77 54.01, 108.77 54.11, 108.58 54.19)))``

**Response:**

.. image:: /_static/cql-filter/example16.png
   :alt: example of cql query filter
   :align: center

* But if needed to extract the information of lakes that are within a particular geometry. Then **WITHIN(geometry,POLYGON((-112.32 49.83, -94.21 49.83, -94.21 59.97, -112.32 59.97, -112.32 49.83)))** will return the features that are within a polygon of specified coordinates.

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&filter-lang=cql-text&`` ``filter=WITHIN(geometry,POLYGON((-112.32 49.83, -94.21 49.83, -94.21 59.97, -112.32 59.97, -112.32 49.83)))``

**Response:**

.. image:: /_static/cql-filter/example17.png
   :alt: example of cql query filter
   :align: center

* To filter all the lakes that lies beyond 10000 meters from a location (-85 75) but its id should be between 15 and 25. Then the query filter can be **BEYOND(geometry,POINT(-85 75),10000,meters) AND id BETWEEN 15 AND 25**

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&limit=5&filter-lang=cql-text&`` ``filter=BEYOND(geometry,POINT(-85 75),10000,meters) AND id BETWEEN 15 AND 25``

**Response:**

.. image:: /_static/cql-filter/example18.png
   :alt: example of cql query filter
   :align: center

* But if to filter all the lakes that lies within 10000 meters from a location (-85 75) but its id should be between 15 and 25. Then the query filter can be **DWITHIN(geometry,POINT(-85 75),10000,meters) AND id BETWEEN 15 AND 25**

**Requested API:**

``http://localhost:5000/collections/lakes/items?f=html&limit=5&filter-lang=cql-text&`` ``filter=DWITHIN(geometry,POINT(-85 75),10000,meters) AND id BETWEEN 15 AND 25``

**Response:**

.. image:: /_static/cql-filter/example19.png
   :alt: example of cql query filter
   :align: center

***No such lakes found*

*The full list of geometric predicates are: EQUALS, DISJOINT, INTERSECTS, TOUCHES, CROSSES, WITHIN, CONTAINS, OVERLAPS, RELATE, DWITHIN, BEYOND*

The CQL extension on pygeoapi supports all the above geometric predicates to perform spatial filters on any feature collection.

Temporal filters
^^^^^^^^^^^^^^^^

* Get all the features whose time value is before a point in time such as **datetime BEFORE 2001-10-30T14:24:54Z**

**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&`` ``filter=datetime BEFORE 2001-10-30T14:24:54Z``

**Response:**

.. image:: /_static/cql-filter/example20.png
   :alt: example of cql query filter
   :align: center

* Get all the features whose time value is during a time period such as **datetime DURING 2003-01-01T00:00:00Z/2005-01-01T00:00:00Z**

**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&`` ``filter=datetime DURING 2003-01-01T00:00:00Z/2005-01-01T00:00:00Z``

**Response:**

.. image:: /_static/cql-filter/example21.png
   :alt: example of cql query filter
   :align: center

* Get all the features whose time value is after a point in time such as **datetime AFTER 2001-10-30T14:24:54Z**

**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&`` ``filter=datetime AFTER 2001-10-30T14:24:54Z``

**Response:**

.. image:: /_static/cql-filter/example22.png
   :alt: example of cql query filter
   :align: center

* Get all the features whose time value is during or after a time period such as **datetime DURING OR AFTER 2003-01-01T00:00:00Z/2005-01-01T00:00:00Z**

**Requested API:**

``http://localhost:5000/collections/obs/items?f=html&filter-lang=cql-text&`` ``filter=datetime DURING OR AFTER 2003-01-01T00:00:00Z/2005-01-01T00:00:00Z``

**Response:**

.. image:: /_static/cql-filter/example23.png
   :alt: example of cql query filter
   :align: center



.. _cql-filter
