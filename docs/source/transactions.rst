.. _transactions:

Transactions
============

pygeoapi supports the `OGC API - Features - Part 4: Create, Replace, Update and Delete`_ draft specification, allowing
for transactional capabilities against feature and record data.

To enable transactions in pygeoapi, a given resource provider needs to be editable (via the configuration resource provider
``editable: true`` property).  Note that the feature or record provider MUST support create/update/delete.  See
:ref:`ogcapi-features` and :ref:`ogcapi-records` for transaction support status of pygeoapi backends.

Access control
^^^^^^^^^^^^^^

It should be made clear that authentication and authorization is beyond the responsibility of pygeoapi.  This means that
if a pygeoapi user enables transactions, they must provide access control explicitly via another service.

.. _`OGC API - Features - Part 4: Create, Replace, Update and Delete`: https://docs.ogc.org/DRAFTS/20-002.html

Validation
^^^^^^^^^^

pygeoapi transaction support includes the option to implement custom validation when adding or updating features or records.

To enable validation in transactions in pygeoapi, a given resource provider can specify a custom validator plugin to implement
custom business rules as needed to ensure data is valid prior to adding or updating a given provider backend.

Given the example below:

.. code-block:: yaml

   providers:
       - type: feature
         name: Elasticsearch
         data: /path/to/file
         id_field: stn_id
         editable: true
         validator:
             name: mycooldatapackage.mycooldatavalidator.MyCoolDataValidator
             # name: GeoJSON  # shipped with pygeoapi, referred to be a shortname

The ``validator.name`` element refers to one of the following:

* a validator plugin that is shipped with pygeoapi (noting that the core
  pygeoapi plugin registry can be found in ``pygeoapi.plugin.PLUGINS``) which can be referred to
  via a shortname
* a custom Python module/class that implements a pygeoapi validator plugin.  See :ref:`plugins`
  for more information on implementing validator plugins.
