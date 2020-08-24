.. _data-transactions:

Simple Data Transactions
========================

pygeoapi supports simple data transactions i.e, modifications that affect a single feature in a single collection.
Simple transactions employ the standard HTTP verbs - POST, PUT, PATCH and DELETE to create, replace, modify and remove features from a collection.

Transaction support is optional and is abscent by default. 
You can enable transaction suport for a provider of type feature under extensions in the pygeoapi config file.
The pygeoapi configuration file *pygeoapi-data-transaction-config.yml* in root directory of pygeoapi project folder includes an example for enabling transaction support in *obs* sample dataset.


Types of Transaction Requests
-----------------------------

The following request types are supported:

#. Insert a new feature item into feature collection
#. Replace an existing feature item from feature collection by id
#. Update an existing feature item from feature collection by id
#. Remove an existing feature item from feature collection by id


Sample Requests
---------------


Insert a new feature item into feature collection
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Request method should be **POST**.
Request URL should be **Collection Items URL** (Eg: http://localhost:5000/collections/obs/items).
Request payload should be in geojson format containing a feature item with same schema as that of items in the collection.
If the payload contain an id field, then a feature item with that id will be added and else a random id will be generated.

Request Header:
"""""""""""""""
``POST http://localhost:5000/collections/obs/items``

Request Payload:
""""""""""""""""
.. code-block:: json

  {
    "geometry": {
      "type": "Point",
      "coordinates": [
        20, 15
      ]
    },
    "properties": {
      "datetime": "2001-10-30T14:24:55Z",
      "stn_id": 35,
      "value": 89.9
    },
    "type": "Feature"
  }


Replace an existing feature item from feature collection by id
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Request method should be **PUT**.
Request URL should be **Collection Item URL** (Eg: http://localhost:5000/collections/obs/items/{featureId}).
Request payload should be a feature item in geojson format with same schema as that of collection items.

Request Header:
"""""""""""""""
``PUT http://localhost:5000/collections/obs/items/{featureId}``

Request Payload:
""""""""""""""""
.. code-block:: json

  {
    "geometry": {
      "type": "Point",
      "coordinates": [
        30, 45
      ]
    },
    "properties": {
      "datetime": "2010-11-13T14:24:55Z",
      "stn_id": 55,
      "value": 99.9
    },
    "type": "Feature"
  }


Update an existing feature item from feature collection by id
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Request method should be **PATCH**
Request URL should be **Collection Item URL** (Eg: http://localhost:5000/collections/obs/items/{featureId}).
Request payload should be in json format which encodes three operations : ``add``, ``modify`` and ``remove``.

Request Header:
"""""""""""""""
``PATCH http://localhost:5000/collections/obs/items/{featureId}``

Request Payload:
""""""""""""""""
.. code-block:: json

  {
    "add": [
      {
        "name": "new_item_name",
        "value": "new_item_value"
      }
    ],
    "modify": [
      {
        "name": "value",
        "value": 199.9
      }
    ],
    "remove": [
      "datetime"
    ]
  }

Note:
"""""
Feature collections with schemaless providers (csv, geojson, etc) can support all three kinds of operations. 
But since ``add`` and ``delete`` operations are schema altering by nature, they wont be supported in schemafull providers (sqlite, postgis, etc).


Remove an existing feature item from feature collection by id
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Request method should be **DELETE**.
Request URL should be **Collection Item URL** (Eg: http://localhost:5000/collections/obs/items/{featureId}).

Request Header:
"""""""""""""""
``DELETE http://localhost:5000/collections/obs/items/{featureId}``

Request Payload:
""""""""""""""""
None


.. _data-transactions

