.. _publishing:

Publishing
==========

Let's start working on integrating your data, metadata, and processes.  pygeoapi provides the capability to
publish vector/coverage data, catalogues, processes and exposing filesystems of geospatial data.

A key component of publishing is the pygeoapi plugin framework (data/metadata providers, processes).  Default/core
plugins are described below.

.. seealso::
   :ref:`plugins` for writing custom plugins.

Data publishing
---------------

Data providers allow for configuring data files, databases, search indexes, other APIs, cloud storage,
to be able to return back data to the pygeoapi API framework in a plug and play fashion.

.. toctree::
   :maxdepth: 2

   ogcapi-features
   ogcapi-coverages
   ogcapi-maps
   ogcapi-tiles
   ogcapi-edr

.. seealso::
   :ref:`configuration` for more information on publishing hidden data.

Metadata publishing
-------------------

Metadata providers work in the same manner as data providers, with a focus on geospatial metadata (data about data).

.. toctree::
   :maxdepth: 2

   ogcapi-records
   stac

.. seealso::
   :ref:`configuration` for more information on publishing hidden metadata.

Process publishing
------------------

In addition to data publishing, pygeoapi also provides the capability to publish
processes that can be executed via the OGC API - Processes standard.

.. toctree::
   :maxdepth: 3

   ogcapi-processes
