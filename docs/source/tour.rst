.. _tour:

Taking a tour of pygeoapi
=========================

At this point, you've installed pygeoapi, set configurations and started the server.

pygeoapi's default configuration comes setup with two simple vector datasets, a STAC collection and a sample
process.  Note that these resources are straightforward examples of pygeoapi's baseline functionality, designed
to get the user up and running with as little barriers as possible.

Let's check things out.  In your web browser, go to http://localhost:5000


Overview
--------

All pygeoapi URLs have HTML and JSON representations.  If you are working through a web browser, HTML
is always returned as the default, whereas if you are working programmatically, JSON is always returned.

To explicitly ask for HTML or JSON, simply add ``f=html`` or ``f=json`` to any URL accordingly.

Each web page provides breadcrumbs for navigating up/down the server's data.  In addition, the upper right
of the UI always has JSON and JSON-LD links to provide you with the current page in JSON if desired.


Landing page
------------

http://localhost:5000

The landing page provides a high level overview of the pygeoapi server (contact information, licensing),
as well as specific sections to browse data, processes and geospatial files.


Collections
-----------

http://localhost:5000/collections

The collections page displays all the datasets available on the pygeoapi server with their title
and abstract.  Let's drill deeper into a given dataset.


Collection information
----------------------

http://localhost:5000/collections/obs

Let's drill deeper into a given dataset.  Here we can see the ``obs`` dataset is described along
with related links (other related HTML pages, dataset download, etc.).

The 'View' section provides the default to start browsing the data.

The 'Queryables' section provides a link to the dataset's properties.

Vector data
-----------

Collection queryables
^^^^^^^^^^^^^^^^^^^^^

http://localhost:5000/collections/obs/queryables

The queryables endpoint provides a list of queryable properties and their associated datatypes.


Collection items
^^^^^^^^^^^^^^^^

http://localhost:5000/collections/obs/items

This page displays a map and tabular view of the data.  Features are clickable on the interactive map,
allowing the user to drill into more information about the feature.  The table also allows for drilling
into a feature by clicking the link in a given table row.

Let's inspect the feature close to `Toronto, Ontario, Canada`_.


Collection item
^^^^^^^^^^^^^^^

http://localhost:5000/collections/obs/items/297

This page provides an overview of the feature and its full set of properties, along with an interactive
map.

.. seealso::
   :ref:`ogcapi-features` for more OGC API - Features request examples.

Raster data
-----------

Collection coverage domainset
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This page provides information on a collection coverage spatial properties and axis information.

http://localhost:5000/collections/gdps-temperature/coverage/domainset

Collection coverage rangetype
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This page provides information on a collection coverage rangetype (bands) information.

http://localhost:5000/collections/gdps-temperature/coverage/rangetype

Collection coverage data
^^^^^^^^^^^^^^^^^^^^^^^^

This page provides a coverage in CoverageJSON format.

http://localhost:5000/collections/gdps-temperature/coverage

.. seealso::
   :ref:`ogcapi-coverages` for more OGC API - Coverages request exampless.

SpatioTemporal Assets
---------------------

http://localhost:5000/stac

This page provides a Web Accessible Folder view of raw geospatial data files.  Users can navigate and
click to browse directory contentsor inspect files.  Clicking on a file will attempt to display the
file's properties/metadata, as well as an interactive map with a footprint of the spatial extent of
the file.

.. seealso::
   :ref:`stac` for more STAC request examples.

Processes
---------

The processes page provides a list of process integrated onto the server, along with a name and description.

.. todo::
   Expand with more info once OAProc HTML is better flushed out.

.. seealso::
   :ref:`ogcapi-processes` for more OGC API - Processes request examples.

API Documentation
-----------------

http://localhost:5000/openapi

http://localhost:5000/openapi?f=json

The API documentation links provide a `Swagger`_ page of the API as a tool for developers to provide example
request/response/query capabilities.  A JSON representation is also provided.

.. seealso::
   :ref:`openapi`


Conformance
-----------

http://localhost:5000/conformance

The conformance page provides a list of URLs corresponding to the OGC API conformance classes supported
by the pygeoapi server.  This information is typically useful for developers and client applications to
discover what is supported by the server.

.. _`Toronto, Ontario, Canada`: https://en.wikipedia.org/wiki/Toronto
.. _`Swagger`: https://en.wikipedia.org/wiki/Swagger_(software)
