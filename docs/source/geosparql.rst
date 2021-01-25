.. _geosparql:

GeoSPARQL endpoint as data provider
===================================

pygeoapi now supports GeoSPARQL as a data provider, albeit still in a limited way. For now only the `get` and `query` operations are supported, but there is more to come.

pygeoapi creates GeoSPARQL queries to retrieve RDF triplets from the GeoSPARQL endpoint in the JSON-LD format. These triplets are then transformed into a GeoJSON document to be returned by the API. The URIs of related ontological classes and other RDF resources are kept in the `properties` section of the GeoJSON document.

Configuration
-------------

The example configuration file in the project root folder includes a collection called `pois` exemplifying how to configure a GeoSPARQL endpoint as provider. Three specific elements are required:

 - `data`: the URL of the GeoSPARQL endpoint.

 - `rdf_type`: the type of RDF individuals that correspond to the collection. pygeoapi expects all the individuals of this type to have a related geometry individual (through the predicate `http://www.opengis.net/ont/geosparql#hasGeometry`).

 - `id_prefix`: the initial segment of the URI for this collection that is the same for all individuals. 

Testing data and endpoint
-------------------------

In the folder `docker/examples/geosparql/data` there a are few simple examples with GeoSPARQL triplets in the Turtle format. They can be imported into a triple store offering a GeoSPARQL endpoint for testing.

The folder `docker/examples/geosparql` contains the resources necessary to set up a GeoSPARQL endpointwith [Virtuoso](https://virtuoso.openlinksw.com/). The `README` file in that folder also provides instructions on how to import the test data into the Virtuoso triple store.




