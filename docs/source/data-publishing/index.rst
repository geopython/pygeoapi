.. _data-publishing:

Resource publishing
===================

Let's start working on integrating your data into pygeoapi.  pygeoapi provides the capability to
publish vector/coverage data, processes, catalogues, and exposing filesystems of geospatial data.

Providers overview
------------------

A key component to data publishing is the pygeoapi provider framework.  Providers allow for
configuring data files, databases, search indexes, other APIs, cloud storage, to be able to
return back data to the pygeoapi API framework in a plug and play fashion.

.. toctree::
   :maxdepth: 2
   :caption: Data publishing
   :name: Data publishing

   ogcapi-features
   ogcapi-coverages
   ogcapi-maps
   ogcapi-tiles
   ogcapi-records
   ogcapi-edr
   stac


Processes overview
------------------

In addition to data publishing, pygeoapi also provides the capability to publish
processes that can be executed via the OGC API - Processes standard.

.. toctree::
   :maxdepth: 3
   :caption: Process publishing
   :name: Process publishing

   ogcapi-processes


.. seealso::
   :ref:`configuration` for more information on publishing hidden resources.
