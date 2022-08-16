.. _ogcapi-routes:

Generating routes via OGC API - Routes or - Processes
=====================================================

`OGC API - Routes`_ provides geospatial routing processing functionality in a standards-based
fashion (inputs, outputs). Alternatively, routes can be generated using `OGC API - Processes`_.

pygeoapi implements routing capabilities by connecting to a routing engine in the backend.
Currently support is implemented for `pgRouting`_, an open source  PostGIS/PostgreSQL-based
routing engine.

A routes processor is provided in the pygeoapi default architecture.

Configuration for OGC API - Routes
----------------------------------

.. code-block:: yaml

    routes:
        type: routes
        title: District of Columbia
        description: Routing engine for DC area created with OpenStreetMap data
        keywords:
            - DC
            - OSM
        extents:
            spatial:
                bbox: [-77.1, 38.83, -76.9, 38.99]
                crs: http://www.opengis.net/def/crs/OGC/1.3/CRS84
        processor:
            name: Routes
            path: /tmp
            engine:
                type: pgRouting
                connection:
                    host: localhost
                    dbname: district-of-columbia
                    user: postgres
                    password: postgres
                    search_path: [public]
                table:
                    ways_id: gid
                    geom_field: the_geom
                search_buffer: 0.01
            preferences: [fastest, shortest]
            modes: [vehicle]
            units:
                speed: mph

Configuration for OGC API - Processes
-------------------------------------

.. code-block:: yaml

    routes-processor:
        type: process
        processor:
            name: Routes
            path: /tmp
            engine:
                type: pgRouting
                connection:
                    host: localhost
                    dbname: district-of-columbia
                    user: postgres
                    password: postgres
                    search_path: [public]
                table:
                    ways_id: gid
                    geom_field: the_geom
                search_buffer: 0.01
            preferences: [fastest, shortest]
            modes: [vehicle]
            units:
                speed: mph

Route Generation
----------------

In order to generate a route, at a minimum two valid waypoints need to be provided.
Additionally, preferences and modes can be specified according to the options offered
by the routing engine. Height, weight and obstacle restrictions can also be added to
the query.

The query to generate a route is similar using OGC API - Routes or - Processes.

Route Exchange Model
--------------------

Generated routes are encoded using the `Route Exchange Model`_, a GeoJSON format that
provides information of a route in a standardized way that is independent of the underlying
data, routing engine software, and algorithms that are used to compute the route.

Route management
----------------

By default, when a route is generated, pygeoapi stores it together with its definition
in the folder provided in the 'path' attribute. OGC API - Routes offers ways to list
existing routes, as well as to fetch or delete specific routes or their definition. Routes
generated using OGC API - Processes will be also available through OGC API - Routes, 
if both APIs are set up in the same instance.

Routing examples
-------------------

* list all preprocessed routes
  * http://localhost:5000/routes
* view route 73cb1511-1da3-11ed-aa80-cd927c279be4
  * http://localhost:5000/routes/73cb1511-1da3-11ed-aa80-cd927c279be4
* view route 73cb1511-1da3-11ed-aa80-cd927c279be4 definition
  * http://localhost:5000/routes/73cb1511-1da3-11ed-aa80-cd927c279be4/definition
* generate a route from the Capitol to the White House in Washington D.C. (using OGC API - Routes)
  * ``curl -X POST "http://localhost:5000/routes" -H "Content-Type: application/json" -d "{\"inputs\":{\"name\": \"test\", \"waypoints\":{\"value\":{\"type\": \"MultiPoint\", \"coordinates\":[[ -77.012034,38.890563],[ -77.033604, 38.899064 ]]}}}}"``
* generate a route from the Capitol to the White House in Washington D.C. (using OGC API - Processes)
  * ``curl -X POST "http://localhost:5000/processes/routes-processor/execution" -H "Content-Type: application/json" -d "{\"inputs\":{\"name\": \"test\", \"waypoints\":{\"value\":{\"type\": \"MultiPoint\", \"coordinates\":[[ -77.012034,38.890563],[ -77.033604, 38.899064 ]]}}}}"``
* delete route 73cb1511-1da3-11ed-aa80-cd927c279be4
  * ``curl -X DELETE "http://localhost:5000/routes/73cb1511-1da3-11ed-aa80-cd927c279be4"``

.. _`OGC API - Routes`: https://github.com/opengeospatial/ogcapi-routes
.. _`OGC API - Processes`: https://github.com/opengeospatial/ogcapi-processes
.. _`Route Exchange Model`: https://portal.ogc.org/files/?artifact_id=100686
.. _`pgRouting`: https://pgrouting.org/
