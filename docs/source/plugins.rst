.. _plugins:

Customizing pygeoapi: plugins
=============================

In this section we will explain how pygeoapi provides plugin architecture for data providers, formatters and processes.

Plugin development requires knowledge of how to program in Python as well as Python's package/module system.

Overview
--------

pygeoapi provides a robust plugin architecture that enables developers to extend functionality.  Infact,
pygeoapi itself implements numerous formats, data providers and the process functionality as plugins.

The pygeoapi architecture supports the following subsystems:

* data providers
* output formats
* processes
* process manager

The core pygeoapi plugin registry can be found in ``pygeoapi.plugin.PLUGINS``.

Each plugin type implements its relevant base class as the API contract:

* data providers: ``pygeoapi.provider.base``
* output formats: ``pygeoapi.formatter.base``
* processes: ``pygeoapi.process.base``
* process_manager: ``pygeoapi.process.manager.base``

.. todo:: link PLUGINS to API doc

Plugins can be developed outside of the pygeoapi codebase and be dynamically loaded
by way of the pygeoapi configuration.  This allows your custom plugins to live outside
pygeoapi for easier maintenance of software updates.

.. note::
   It is recommended to store pygeoapi plugins outside of pygeoapi for easier software
   updates and package management


Connecting plugins to pygeoapi
------------------------------

The following methods are options to connect a plugin to pygeoapi:

**Option 1**: implement outside of pygeoapi and add to configuration (recommended)

* Create a Python package with the plugin code (see `Cookiecutter`_ as an example)
* Install this Python package onto your system (``python3 setup.py install``).  At this point your new package
  should be in the ``PYTHONPATH`` of your pygeoapi installation
* Specify the main plugin class as the ``name`` of the relevant type in the
pygeoapi configuration. For example, for a new vector data provider:

.. code-block:: yaml

   providers:
       - type: feature
         # name may refer to an external Python class, that is loaded by pygeoapi at runtime
         name: mycooldatapackage.mycoolvectordata.MyCoolVectorDataProvider
         data: /path/to/file
         id_field: stn_id


.. note::  The United States Geological Survey has created a Cookiecutter project for creating pygeoapi plugins. See the `pygeoapi-plugin-cookiecutter`_ project to get started.

**Option 2**: Update in core pygeoapi:

* Copy your plugin code into the pygeoapi source code directory - for example, if it is a provider plugin, copy it
  to ``pygeoapi/provider``
* Update the plugin registry in ``pygeoapi/plugin.py:PLUGINS['provider']`` with the plugin's
  shortname (say ``MyCoolVectorData``) and dotted path to the class (i.e. ``pygeoapi.provider.mycoolvectordata.MyCoolVectorDataProvider``)
* Specify in your dataset provider configuration as follows:

.. code-block:: yaml

   providers:
       - type: feature
         # name may also refer to a known core pygeopai plugin
         name: MyCoolVectorData
         data: /path/to/file
         id_field: stn_id


Customizing pygeoapi process manager
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The pygeoapi process manager may also be customized. Similarly to the provider plugins, you may use the pygeoapi
configuration's ``server.manager.name`` to indicate either the dotted path to the python package and the relevant
manager class (*i.e.* similar to option 1 above) or the name of a known core pygeoapi plugin (*i.e.*, similar to
option 2 above).






Example: custom pygeoapi vector data provider
---------------------------------------------

Lets consider the steps for a vector data provider plugin (source code is located here: :ref:`data Provider`).

Python code
^^^^^^^^^^^

The below template provides a minimal example (let's call the file ``mycoolvectordata.py``:

.. code-block:: python

   from pygeoapi.provider.base import BaseProvider

   class MyCoolVectorDataProvider(BaseProvider):
       """My cool vector data provider"""

       def __init__(self, provider_def):
           """Inherit from parent class"""

           super().__init__(provider_def)

       def get_fields(self):

           # open dat file and return fields and their datatypes
           return {
               'field1': 'string',
               'field2': 'string'
           }

       def query(self, offset=0, limit=10, resulttype='results',
                 bbox=[], datetime_=None, properties=[], sortby=[],
                 select_properties=[], skip_geometry=False, **kwargs):

           # optionally specify the output filename pygeoapi can use as part
           # of the response (HTTP Content-Disposition header)
           self.filename = "my-cool-filename.dat"

           # open data file (self.data) and process, return
           return {
               'type': 'FeatureCollection',
               'features': [{
                   'type': 'Feature',
                   'id': '371',
                   'geometry': {
                       'type': 'Point',
                       'coordinates': [ -75, 45 ]
                   },
                   'properties': {
                       'stn_id': '35',
                       'datetime': '2001-10-30T14:24:55Z',
                       'value': '89.9'
                   }
               }]
           }

       def get_schema():
           # return a `dict` of a JSON schema (inline or reference)
           return ('application/geo+json', {'$ref': 'https://geojson.org/schema/Feature.json'})


For brevity, the above code will always return the single feature of the dataset.  In reality, the plugin
developer would connect to a data source with capabilities to run queries and return a relevant result set,
as well as implement the ``get`` method accordingly.  As long as the plugin implements the API contract of
its base provider, all other functionality is left to the provider implementation.

Each base class documents the functions, arguments and return types required for implementation.

.. note::  You can add language support to your plugin using :ref:`these guides<language>`.

.. note::  You can let the pygeoapi core do coordinate transformation for `crs` queries using the `@crs_transform` Decorator on `query()` and `get()` methods. See :ref:`crs`.


Example: custom pygeoapi raster data provider
---------------------------------------------

Lets consider the steps for a raster data provider plugin (source code is located here: :ref:`data Provider`).

Python code
^^^^^^^^^^^

The below template provides a minimal example (let's call the file ``mycoolrasterdata.py``:

.. code-block:: python

   from pygeoapi.provider.base import BaseProvider

   class MyCoolRasterDataProvider(BaseProvider):
       """My cool raster data provider"""

       def __init__(self, provider_def):
           """Inherit from parent class"""

           super().__init__(provider_def)
           self.num_bands = 4
           self.axes = ['Lat', 'Long']

       def get_coverage_domainset(self):
           # return a CIS JSON DomainSet

       def get_coverage_rangetype(self):
           # return a CIS JSON RangeType

       def query(self, bands=[], subsets={}, format_='json', **kwargs):
           # process bands and subsets parameters
           # query/extract coverage data

           # optionally specify the output filename pygeoapi can use as part
           of the response (HTTP Content-Disposition header)
           self.filename = "my-cool-filename.dat"

           if format_ == 'json':
               # return a CoverageJSON representation
               return {'type': 'Coverage', ...}  # trimmed for brevity
           else:
               # return default (likely binary) representation
               return bytes(112)

For brevity, the above code will always JSON for metadata and binary or CoverageJSON for the data.  In reality, the plugin
developer would connect to a data source with capabilities to run queries and return a relevant result set,
As long as the plugin implements the API contract of its base provider, all other functionality is left to the provider
implementation.

Each base class documents the functions, arguments and return types required for implementation.


Example: custom pygeoapi formatter
----------------------------------

Python code
^^^^^^^^^^^

The below template provides a minimal example (let's call the file ``mycooljsonformat.py``:

.. code-block:: python

   import json
   from pygeoapi.formatter.base import BaseFormatter

   class MyCoolJSONFormatter(BaseFormatter):
       """My cool JSON formatter"""

       def __init__(self, formatter_def):
           """Inherit from parent class"""

           super().__init__({'name': 'cooljson', 'geom': None})
           self.mimetype = 'application/json; subtype:mycooljson'

       def write(self, options={}, data=None):
           """custom writer"""

           out_data {'rows': []}

           for feature in data['features']:
               out_data.append(feature['properties'])

           return out_data


Processing plugins
------------------

Processing plugins are following the OGC API - Processes development.  Given that the specification is
under development, the implementation in ``pygeoapi/process/hello_world.py`` provides a suitable example
for the time being.


Featured plugins
----------------

The following plugins provide useful examples of pygeoapi plugins implemented
by downstream applications.

.. csv-table::
   :header: "Plugin(s)", "Organization/Project","Description"
   :align: left

   `msc-pygeoapi`_,Meteorological Service of Canada,processes for weather/climate/water data workflows
   `pygeoapi-kubernetes-papermill`_,Euro Data Cube,processes for executing Jupyter notebooks via Kubernetes
   `local-outlier-factor-plugin`_,Manaaki Whenua – Landcare Research,processes for local outlier detection
   `ogc-edc`_,Euro Data Cube,coverage provider atop the EDC API
   `nldi_xstool`_,United States Geological Survey,Water data processing
   `pygeometa-plugin`_,pygeometa project,pygeometa as a service


.. _`Cookiecutter`: https://github.com/audreyfeldroy/cookiecutter-pypackage
.. _`msc-pygeoapi`: https://github.com/ECCC-MSC/msc-pygeoapi
.. _`pygeoapi-kubernetes-papermill`: https://github.com/eurodatacube/pygeoapi-kubernetes-papermill
.. _`local-outlier-factor-plugin`: https://github.com/manaakiwhenua/local-outlier-factor-plugin
.. _`ogc-edc`: https://github.com/eurodatacube/ogc-edc/tree/oapi/edc_ogc/pygeoapi
.. _`nldi_xstool`: https://code.usgs.gov/wma/nhgf/toolsteam/nldi-xstool
.. _`pygeoapi-plugin-cookiecutter`: https://code.usgs.gov/wma/nhgf/pygeoapi-plugin-cookiecutter
.. _`pygeometa-plugin`: https://geopython.github.io/pygeometa/pygeoapi-plugin
