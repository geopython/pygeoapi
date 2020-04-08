.. _introduction:

Introduction
============

pygeoapi is a Python server implementation of the OGC API suite of standards. The project emerged as part of the next generation `OGC API`_ efforts in 2018 and provides the capability for organizations to deploy a RESTful OGC API endpoint using OpenAPI, GeoJSON, and HTML. pygeoapi is `open source <https://opensource.org>`_ and released under an MIT :ref:`license`.

Features
--------

- out of the box modern OGC API server
- certified OGC Compliant and Reference Implementation for OGC API - Features
- additionally implements OGC API - Processes and SpatioTemporal Asset Library
- out of the data provider plugins for GDAL/OGR, Elasticsearch, PostgreSQL/PostGIS
- easy to use OpenAPI / Swagger documentation for developers
- supports JSON, GeoJSON, HTML and CSV output
- supports data filtering by spatial, temporal or attribute queries
- easy to install: install a full implementation via pip or git
- simply YAML configuration
- easy to deploy: via UbuntuGIS or the official Docker image
- flexible: built on a robust plugin framework to build custom data connections, formats and processes
- supports any Python web framework (included are Flask [default], Starlette)

Standards Support
-----------------

Standards are at the core of pygeoapi.  Below is the project's standards support matrix.

- Implementing: implements standard (good)
- Compliant: conforms to OGC compliance requirements (great)
- Reference Implementation: provides a reference for the standard (awesome!)

.. csv-table::
   :header: "Standard", "Support"
   :align: left
   :widths: 20, 20

   `OGC API - Features`_,Reference Implementation
   `OGC API - Processes`_,Implementing
   `SpatioTemporal Asset Catalog`_,Implementing


.. _`OGC API`: http://ogcapi.org
.. _`OGC API - Features`: https://www.ogc.org/standards/ogcapi-features
.. _`OGC API - Processes`: https://github.com/opengeospatial/wps-rest-binding
.. _`SpatioTemporal Asset Catalog`: https://stacspec.org/
