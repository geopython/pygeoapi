.. _openapi:

OpenAPI
=======

The `OpenAPI specification <https://swagger.io/docs/specification/about/>`_ is an open specification for RESTful
endpoints.  OGC API specifications leverage OpenAPI to describe the API in great detail with developer focus.

The RESTful structure and payload are defined using JSON or YAML file structures (pygeoapi uses YAML).  The basic
structure is described here: `<https://swagger.io/docs/specification/basic-structure/>`_

The official OpenAPI specification can be found `on GitHub <https://github.com/OAI/OpenAPI-Specification/tree/master/versions>`_.
pygeoapi supports OpenAPI version 3.0.2.

As described in :ref:`administration`, the pygeoapi OpenAPI document is automatically generated based on the
configuration file:

The API is accessible at the ``/openapi`` endpoint, providing a Swagger-based webpage of the API description..

.. seealso::
   the pygeoapi demo OpenAPI/Swagger endpoint at https://demo.pygeoapi.io/master/openapi


Using OpenAPI
-------------

Accessing the Swagger webpage we have the following structure:

.. image:: /_static/openapi_intro_page.png


Notice that each dataset is represented as a RESTful endpoint under ``collections``.

In this example we will test ``GET`` capability of data concerning windmills in the Netherlands.  Let's start by
accessing the service's dataset collections:

.. image:: /_static/openapi_get_collections.png

The service collection metadata will contain a description of each collection:

.. image:: /_static/openapi_get_collections_result.png

Here, we see that the ``dutch_windmills`` dataset is be available.  Next, let's obtain the specific metadata of the
dataset:

.. image:: /_static/openapi_get_collection.png

.. image:: /_static/openapi_get_collection_result.png

We also see that the dataset has an ``items`` endpoint which provides all data, along with specific parameters for
filtering,
paging and sorting:

.. image:: /_static/openapi_get_item.png

For each item in our dataset we have a specific identifier.  Notice that the identifier is not part of the GeoJSON
properties, but is provided as a GeoJSON root property of ``id``.

.. image:: /_static/openapi_get_item_id.png

This identifier can be used to obtain a specific item from the dataset using the ``items{id}`` endpoint as follows:

.. image:: /_static/openapi_get_item_id2.png

Summary
-------

Using pygeoapi's OpenAPI and Swagger endpoints provides a useful user interface to query data, as well as for
developers to easily understand pygeoapi when building downstream applications.
