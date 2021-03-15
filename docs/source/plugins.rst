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

- data providers
- output formats
- processes

The core pygeoapi plugin registry can be found in ``pygeoapi.plugin.PLUGINS``.

Each plugin type implements its relevant base class as the API contract:

- data providers: ``pygeoapi.provider.base``
- output formats: ``pygeoapi.formatter.base``
- processes: ``pygeoapi.process.base``

.. todo:: link PLUGINS to API doc

Plugins can be developed outside of the pygeoapi codebase and be dynamically loaded
by way of the pygeoapi configuration.  This allows your custom plugins to live outside
pygeoapi for easier maintenance of software updates.

.. note::
   It is recommended to store pygeoapi plugins outside of pygeoapi for easier software
   updates and package management


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

       def __init__(self, provider_def, requested_locale=None):
           """Inherit from parent class"""

           super().__init__(provider_def, requested_locale)

       def get_fields(self):

           # open dat file and return fields and their datatypes
           return {
               'field1': 'string',
               'field2': 'string'
           }

       def query(self,startindex=0, limit=10, resulttype='results',
                 bbox=[], datetime_=None, properties=[], sortby=[],
                 select_properties=[], skip_geometry=False):

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


For brevity, the above code will always return the single feature of the dataset.  In reality, the plugin
developer would connect to a data source with capabilities to run queries and return a relevant result set,
as well as implement the ``get`` method accordingly.  As long as the plugin implements the API contract of
its base provider, all other functionality is left to the provider implementation.

Each base class documents the functions, arguments and return types required for implementation.

.. note::   You can add language support to your plugin using :ref:`these guides<language>`.


Connecting to pygeoapi
^^^^^^^^^^^^^^^^^^^^^^

The following methods are options to connect the plugin to pygeoapi:

**Option 1**: Update in core pygeoapi:

- copy ``mycoolvectordata.py`` into ``pygeoapi/provider``
- update the plugin registry in ``pygeoapi/plugin.py:PLUGINS['provider']`` with the plugin's
  shortname (say ``MyCoolVectorData``) and dotted path to the class (i.e. ``pygeoapi.provider.mycoolvectordata.MyCoolVectorDataProvider``)
- specify in your dataset provider configuration as follows:

.. code-block:: yaml

   providers:
       - type: feature
         name: MyCoolVectorData
         data: /path/to/file
         id_field: stn_id


**Option 2**: implement outside of pygeoapi and add to configuration (recommended)

- create a Python package of the ``mycoolvectordata.py`` module (see `Cookiecutter`_ as an example)
- install your Python package onto your system (``python setup.py install``).  At this point your new package
  should be in the ``PYTHONPATH`` of your pygeoapi installation
- specify in your dataset provider configuration as follows:

.. code-block:: yaml

   providers:
       - type: feature
         name: mycooldatapackage.mycoolvectordata.MyCoolVectorDataProvider
         data: /path/to/file
         id_field: stn_id

BEGIN

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

       def query(self, bands=[], subsets={}, format_='json'):
           # process bands and subsets parameters
           # query/extract coverage data
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

END

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
           self.mimetype = 'text/json; subtype:mycooljson'

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


.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter-pypackage
.. _`msc-pygeoapi`: https://github.com/ECCC-MSC/msc-pygeoapi
.. _`pygeoapi-kubernetes-papermill`: https://github.com/eurodatacube/pygeoapi-kubernetes-papermill
.. _`local-outlier-factor-plugin`: https://github.com/manaakiwhenua/local-outlier-factor-plugin
.. _`ogc-edc`: https://github.com/eurodatacube/ogc-edc/tree/oapi/edc_ogc/pygeoapi
