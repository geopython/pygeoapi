.. _ogcapi-mfapi:

Publishing data to OGC API - MF-API
=====================================

`OGC API - MF-API`_ provides provides a uniform way to access, communicate, and 
anage data about moving features across different applications, data providers, 
and data consumers.

To add moving features data to pygeoapi for standard interfaces, 
which is defined in the OGC API - MovingFeatures - Part 1:Core.
you can use the dataset example in `Building Blocks specified in OGC API - Moving Features - Part 1 Core (1.0.0)`_ 
as a baseline and modify accordingly.

Configuration
-------------

In order to register data for Moving features, the DB must be created and the related tables must be initially set up.


PostgreSQL
^^^^^^^^^^
.. note::
   Requires Python packages pymeos

Must have PostGIS installed and uuid-ossp

.. code-block:: yaml

   server:
       manager:
           name: PostgreSQL
           connection:
               host: localhost
               port: 5432
               database: mobilitydb
               user: postgres
               password: ${POSTGRESQL_PASSWORD:-postgres}

.. note::
   To run the process, create a table with `DDL <https://github.com/ogi-ts-shimizu/pygeoapi-ogi-mf-api/blob/mf-api-updates/tests/data/mf-api.sql>`_

   
.. code-block:: sh
   
   psql -U postgres -h 127.0.0.1 -p 5432 mobilitydb < tests/data/mf-api.sql


Processing examples
-------------------

.. note::
  `Here <https://github.com/ogi-ts-shimizu/pygeoapi-ogi-mf-api/tree/mf-api-updates/tests/data>`_ is the sample data specified by the -d option of the curl command.

.. code-block:: sh

   # Register metadata about a collection of moving features.
   curl -X POST http://localhost:5000/collections \
        -H "Content-Type: application/json" \
        -d "{\"title\": \"moving_feature_collection_sample\",
            \"updateFrequency\": 1000,
            \"description\": \"example\",
            \"itemType\": \"movingfeature\"
            }"

   # Retrieve catalogs of a moving features collection.
   curl http://localhost:5000/collections


   # Insert a set of moving features or a moving feature into a collection with id {collectionId}.
   curl -X POST http://localhost:5000/collections/{collectionId}/items \
        -H "Content-Type: application/json" \
        -d  @mfapi_moving_feature.json

   # Access a static data of a moving feature with id {mFeatureId}.
   curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}

  # Add more movement data into a moving feature with id {mFeatureId}.
    curl -X POST http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tgsequence \
    -H "Content-Type: application/json" \
    -d  @mfapi_temporal_geometry.json

  # Retrieve the movement data of the single moving feature
  curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tgsequence

  # Get a time-to-(distance,velocity,acceleration) curve of a temporal primitive geometry
  curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}/distance
  curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}/velocity
  curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}/acceleration

  # Add new temporal property data into a moving feature with id {mFeatureId}.
  curl -X POST http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tproperties \
  -H "Content-Type: application/json" \
  -d  @mfapi_temporal_properties.json

  # Retrieve a set of the temporal property data
  curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tproperties

  # Add temporal primitive value data.
  curl -X POST http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tproperties/{tPropertyName} \
  -H "Content-Type: application/json" \
  -d  @mfapi_temporal_property_value_data.json

  # Retrieve a set of the temporal property data
  curl http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tproperties/{tPropertyName}

  # Delete a singe temporal primitive value
  curl -X DELETE http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tproperties/{tPropertyName}/{tValueId}

  # Delete a specified temporal property
  curl -X DELETE http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tproperties/{tPropertyName}

  # Delete a singe temporal primitive geometry
  curl -X DELETE http://localhost:5000/collections/{collectionId}/items/{mFeatureId}/tgsequence/{tGeometryId}

  # Delete a single moving feature
  curl -X DELETE http://localhost:5000/collections/{collectionId}/items/{mFeatureId}
  
  # Delete the collection
  curl -X DELETE http://localhost:5000/collections/{collectionId}


.. _`OGC API - MF-API`: https://github.com/aistairc/pygeoapi-mf-api
.. _`Building Blocks specified in OGC API - Moving Features - Part 1 Core (1.0.0)`: https://developer.ogc.org/api/movingfeatures/index.html#tag/MovingFeatureCollection/operation/registerMetadata
.. _`see website`: https://mobilitydb.com/