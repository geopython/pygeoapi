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


Example: custom pygeoapi data provider
--------------------------------------

Lets consider the steps for a data provider plugin (source code is located here: :ref:`data Provider`).

Python code
^^^^^^^^^^^

The below template provides a minimal example (let's call the file ``mycooldata.py``:

.. code-block:: python

   from pygeoapi.provider.base import BaseProvider

   class MyCoolDataProvider(BaseProvider):
       """My cool data provider"""
      
       def __init__(self, provider_def):
           """Inherit from parent class"""

           BaseProvider.__init__(self, provider_def)


       def query(self, startindex=0, limit=10, resulttype='results',
                 bbox=[], datetime=None, properties=[], sortby=[]):

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
developer would connect to a data source with capabilities to run queries and return relevant a result set,
as well as implement the ``get`` method accordingly.  As long as the plugin implements the API contract of
its base provider, functionality is left to the provider implementation.

Each base class documents the functions, arguments and return types required for implementation.

Connecting to pygeoapi
^^^^^^^^^^^^^^^^^^^^^^

The following methods are options to connect the plugin to pygeoapi:

**Option 1**: Update in core pygeoapi:

- copy mycooldata.py into ``pygeoapi/provider``
- update the plugin registry in ``pygeoapi/plugin.py:PLUGINS['provider']`` with the plugin's
  shortname (say ``MyCoolData``) and dotted path to the class (i.e. ``pygeoapi.provider.mycooldata.MyCoolDataProvider``)
- specify in your dataset provider configuration as follows:

.. code-block:: yaml

   provider:
       name: MyCoolData
       data: /path/to/file
       id_field: stn_id


** Option 2**: implement outside of pygeoapi and add to configuration (recommended)

- create a Python package of the mycooldata.py module (see `Cookiecutter`_ as an example)
- install your Python package onto your system (`python setup.py install`).  At this point your new package
  should be in the ``PYTHONPATH`` of your pygeoapi installation
- specify in your dataset provider configuration as follows:

.. code-block:: yaml

   provider:
       name: mycooldatapackage.mycooldata.MyCoolDataProvider
       data: /path/to/file
       id_field: stn_id

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

           BaseFormatter.__init__(self, {'name': 'cooljson', 'geom': None})
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


.. _`Cookiecutter`: https://github.com/audreyr/cookiecutter-pypackage
