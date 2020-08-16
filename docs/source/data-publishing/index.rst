.. _data-publishing:

Data publishing
===============

Let's start working on integrating your data into pygeoapi.  pygeoapi provides the capability to
publish vector data, processes, and exposing filesystems of geospatial data.

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
   ogcapi-processes
   stac
