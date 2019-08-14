.. _openapi:

OpenAPI
=======


`OpenAPI spec <https://swagger.io/docs/specification/about/>`_ is an open specification for REST end points, currentely OGC services are being redefined using such specification.
The REST structure and payload are defined using yaml file structures, the file structure is described here: `<https://swagger.io/docs/specification/basic-structure/>`_

pygeoapi REST end points descriptions on OpenAPI standard are automatically generated based on the configuration file:

 
.. code-block:: console

   pygeoapi generate-openapi-document -c local.config.yml > openapi.yml
   

The api will them be accessible at `/api` endpoint.

For api demo please check: `<https://demo.pygeoapi.io/master/api>`_

The api page has REST description but also integrated clients that can be used to send requests to the REST end points and  see the response provided


Using OpenAPI
-------------

Acessing the openAPI webpage we have the following structure:

.. image:: /_static/openapi_intro_page.png

Please notice that **each dataset** will be represented as a REST end point under `collections`


In this example we will test and `GET`  data concerning windmills in the Netherlands, first we will check the avaiable datasets,
by accessing the service's collections:


.. image:: /_static/openapi_get_collections.png

The service collection metadata will contain a description of the collections provided by the server

.. image:: /_static/openapi_get_collections_result.png

The dataset `dutch_windmills` will be available on the `collections` end point, in the following example we'll obtain the specific metadata of the dataset

.. image:: /_static/openapi_get_collection.png

.. image:: /_static/openapi_get_collection_result.png


features/items composing the data are agregated on the `/items` end point, in this REST end point it is possible to obtain all dataset, or restrict
it features/items to a **numerical limit**, **bounding box**, **time stamp**, **pagging** (start index) 

.. image:: /_static/openapi_get_item.png

For each feature in dataset we have a **specific identifier** (notice that the identifier is not part of the JSON properties),

.. image:: /_static/openapi_get_item_id.png

This identifier can be used to obtain a specific item from the dataset using the `items\{id}` end point as follows:

.. image:: /_static/openapi_get_item_id2.png

