.. _plugins:

Customizing pygeoapi: plugins
=============================

In this section we will explain how pygeoapi provides plugin architecture for data providers, formatters and processes.

Plugin development requires knowledge of how to program in Python as well as Python's package/module system.

.. seealso::
   :ref:`publishing` for configuration of default plugins.

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

* data providers:

  * features/records/maps: ``pygeoapi.provider.base.BaseProvider``
  * edr: ``pygeoapi.provider.base_edr.BaseEDRProvider``
  * tiles: ``pygeoapi.provider.tile.BaseTileProvider``

* output formats: ``pygeoapi.formatter.base.BaseFormatter``
* processes: ``pygeoapi.process.base.BaseProcessor``
* process_manager: ``pygeoapi.process.manager.base.BaseManager``

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
* Install this Python package onto your system (``pip3 install .``).  At this point your new package
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


Specifying custom pygeoapi CLI commands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Third-party plugins may also provide custom CLI commands. This can be done by means of two additional steps:

1. Create your CLI commands using click
2. In your plugin's ``setup.py`` or ``pyproject.toml`` file, specify an entrypoint for the ``pygeoapi`` group
   pointing to your click CLI command or group.

As a simple example, lets imagine you develop a plugin named ``myplugin``, which has a ``cli.py`` module with
the following contents:

.. code-block:: python

   # module: myplugin.cli
   import click

   @click.command(name='super-command')
   def my_cli_command():
       print('Hello, this is my custom pygeoapi CLI command!')


Then, in your plugin's ``setup.py`` file, specify the entrypoints section:

.. code-block:: python

   # file: setup.py
   entry_points={
       'pygeoapi': ['my-plugin = myplugin.cli:my_cli_command']
   }

Alternatively, if using a ``pyproject.toml`` file instead:

.. code-block:: python

   # file: pyproject.toml
   # Noter that this example uses poetry, other Python projects may differ in
   # how they expect entry_points to be specified
   [tool.poetry.plugins.'pygeoapi']
   my-plugin = 'myplugin.cli:my_cli_command'


After having installed this plugin, you should now be able to call the CLI command by running:

.. code-block:: sh

   $ pygeoapi plugins super-command
   Hello, this is my custom pygeoapi CLI command!


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

Let's consider the steps for a vector data provider plugin:

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
           self.filename = 'my-cool-filename.dat'

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

Let's consider the steps for a raster data provider plugin:

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
           self.get_fields()

       def get_fields(self):
           # generate a JSON Schema of coverage band metadata
           self._fields = {
               'b1': {
                   'type': 'number'
               }
           }
           return self._fields

       def query(self, bands=[], subsets={}, format_='json', **kwargs):
           # process bands and subsets parameters
           # query/extract coverage data

           # optionally specify the output filename pygeoapi can use as part
           of the response (HTTP Content-Disposition header)
           self.filename = 'my-cool-filename.dat'

           if format_ == 'json':
               # return a CoverageJSON representation
               return {'type': 'Coverage', ...}  # trimmed for brevity
           else:
               # return default (likely binary) representation
               return bytes(112)

For brevity, the above code will always return JSON for metadata and binary or CoverageJSON for the data.  In reality, the plugin
developer would connect to a data source with capabilities to run queries and return a relevant result set,
As long as the plugin implements the API contract of its base provider, all other functionality is left to the provider
implementation.

Each base class documents the functions, arguments and return types required for implementation.

.. _example-custom-pygeoapi-processing-plugin:

Example: custom pygeoapi EDR data provider
------------------------------------------

Let's consider the steps for an EDR data provider plugin:

Python code
^^^^^^^^^^^

The below template provides a minimal example (let's call the file ``mycooledrdata.py``:

.. code-block:: python

   from pygeoapi.provider.base_edr import BaseEDRProvider

   class MyCoolEDRDataProvider(BaseEDRProvider):

       def __init__(self, provider_def):
           """Inherit from the parent class"""

           super().__init__(provider_def)

           self.covjson = {...}

       def instances(self):
           return ['foo', 'bar']

       def instance(self, instance):
           return instance in instances()

       def position(self, **kwargs):
           return self.covjson

       def trajectory(self, **kwargs):
           return self.covjson


For brevity, the ``position`` function returns ``self.covjson`` which is a
dictionary of a CoverageJSON representation.  ``instances`` returns a list
of instances associated with the collection/plugin, and ``instance`` returns
a boolean of whether a given instance exists/is valid.  EDR query types are subject
to the query functions defined in the plugin.  In the example above, the plugin
implements ``position`` and ``trajectory`` queries, which will be advertised as
supported query types.


Example: custom pygeoapi processing plugin
------------------------------------------

Let's consider a simple process plugin to calculate a square root from a number:

Python code
^^^^^^^^^^^

The below template provides a minimal example (let's call the file ``mycoolsqrtprocess.py``:

.. code-block:: python

   import math

   from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

   PROCESS_METADATA = {
       # reduced for brevity (see examples of PROCESS_METADATA in pygeoapi/process/hello_world.py)
   }

   class MyCoolSqrtProcessor(BaseProcessor)
       """My cool sqrt process plugin"""

       def __init__(self, processor_def):
           """
           Initialize object

           :param processor_def: provider definition

           :returns: pygeoapi.process.mycoolsqrtprocess.MyCoolSqrtProcessor
           """

           super().__init__(processor_def, PROCESS_METADATA)

       def execute(self, data):

           mimetype = 'application/json'
           number = data.get('number')

           if number is None:
               raise ProcessorExecuteError('Cannot process without a number')

           try:
               number = float(data.get('number'))
           except TypeError:
               raise ProcessorExecuteError('Number required')

           value = math.sqrt(number)

           outputs = {
               'id': 'sqrt',
               'value': value
           }

           return mimetype, outputs

       def __repr__(self):
           return f'<MyCoolSqrtProcessor> {self.name}'


The example above handles a dictionary of the JSON payload passed from the client, calculates the square root of a float or integer, and returns the result in an output JSON payload.  The plugin is responsible for defining the expected inputs and outputs in ``PROCESS_METADATA`` and to return the output in any format along with the corresponding media type.


Documenting process metadata
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When defining a process, various metadata must be supplied in order to enable discovery and description
of inputs and outputs.  The metadata is realized by a Python dictionary in a given process that is
supplied to process initialization at runtime.

Below is a sample process definition as a Python dictionary:

.. code-block:: python

   PROCESS_METADATA = {
       'version': '0.2.0',  # the version of the process
       'id': 'hello-world', # process identifier
       'title': 'Hello World',  # process title, can also be multilingual
       'description': 'An example process that takes a name as input, and echoes '  # process description, can also be multilingual
                      'it back as output. Intended to demonstrate a simple '
                      'process with a single literal input.',
       'jobControlOptions': ['sync-execute', 'async-execute'],  # whether the process can be executed in sync or async mode
       'outputTransmission': ['value', 'reference'],  # whether the process can return inline data or URL references
       'keywords': ['hello world', 'example', 'echo'],  # keywords associated with the process
       'links': [{  # a list of 1..n  # link objects relevant to the process
           'type': 'text/html',
           'rel': 'about',
           'title': 'information',
           'href': 'https://example.org/process',
           'hreflang': 'en-US'
       }],
       'inputs': {  # process inputs (one key per input), structured as JSON Schema
           'name': {
               'title': 'Name',
               'description': 'The name of the person or entity that you wish to'
                              'be echoed back as an output',
               'schema': {
                   'type': 'string'
               },
               'minOccurs': 1,
               'maxOccurs': 1,
               'keywords': ['full name', 'personal']
           },
           'message': {
               'title': 'Message',
               'description': 'An optional message to echo as well',
               'schema': {
                   'type': 'string'
               },
               'minOccurs': 0,
               'maxOccurs': 1,
               'keywords': ['message']
           }
       },
       'outputs': {  # outputs
           'echo': {  # an identifier for the output
               'title': 'Hello, world',
               'description': 'A "hello world" echo with the name and (optional)'
                              ' message submitted for processing',
               'schema': {  # output definition, structured as JSON Schema
                   'type': 'object',
                   'contentMediaType': 'application/json'
               }
           }
       },
       'example': {  # example request payload
           'inputs': {
               'name': 'World',
               'message': 'An optional message.',
           }
       }
   }


.. note::

   Additional processing plugins can also be found in ``pygeoapi/process``.

.. _example-custom-pygeoapi-formatter:

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
           self.f = 'cooljson'  # f= value
           self.mimetype = 'application/json; subtype:mycooljson'  # response media type
           self.attachment = False  # whether to provide as an attachment (default False)
           self.extension = 'cooljson'  # filename extension if providing as an attachment

       def write(self, options={}, data=None):
           """custom writer"""

           out_data = {'rows': []}

           for feature in data['features']:
               out_data['rows'].append(feature['properties'])

           return out_data


Example: transaction validation with PluginContext
--------------------------------------------------

pygeoapi serves the schema of each collection at ``/collections/{id}/schema``, but
when a transaction (create/update) comes in, providers write the data without validating
it against that schema.

If you want to fill this gap then you should write a dedicated plugin, i.e. a
``ValidatedGeoJSONProvider`` plugin for the ``GeoJSON`` provider.  It reads the provider's
JSON Schema (from ``get_fields()``) and builds a validator that checks incoming features
on ``create()`` and ``update()``.  In python there are plenty of data validation libraries
but pygeoapi aims at being dependency least so at first glance the provider code should be
**technology-agnostic**: it calls the validator's interface without knowing whether the
validator is implemented with dataclasses, pydantic, or any other library.

The bare minimal, without injecting any ``PluginContext``, is to build a new provider
(or add the validation logic to the existing one) using the standard python and the
existing dependencies to validate from its own fields.
With ``PluginContext``, a downstream project can inject a different validator — for
example one built with pydantic that adds stricter constraints — without changing the
provider code.

The provider plugin
^^^^^^^^^^^^^^^^^^^

The provider resolves its validator in this order:

1. ``context.feature_validator`` if a ``ValidatingContext`` is injected
2. A validator built from the provider's own JSON Schema (default fallback)

The only interface the provider expects is that the validator is callable with
``**properties`` as keyword arguments and raises on invalid data.  This makes the
provider invariant to the validation technology used.

.. code-block:: python

   from pygeoapi.provider.geojson import GeoJSONProvider


   class ValidatedGeoJSONProvider(GeoJSONProvider):
       """GeoJSON provider with transaction validation."""

       def __init__(self, provider_def, context: Optional[PluginContext] = None):
           super().__init__(provider_def, context)

           # Resolve: injected validator or auto-built default
           if (context and hasattr(context, 'feature_validator')
                   and context.feature_validator is not None):
               self._feature_validator = context.feature_validator
           else:
               self._feature_validator = build_feature_validator(
                   self.fields
               )

       def _validate_feature(self, feature):
           """Validate feature properties.

           The validator is called with **properties.
           It may be a dataclass, a pydantic model, or any
           callable that raises on invalid input.
           """

           if self._feature_validator is None:
               return
           properties = feature.get('properties', {})
           self._feature_validator(**properties)

       def create(self, new_feature):
           self._validate_feature(new_feature)
           return super().create(new_feature)

       def update(self, identifier, new_feature):
           self._validate_feature(new_feature)
           return super().update(identifier, new_feature)

Default validator (standard library only)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default validator uses only dataclasses and ``validate_type`` from pygeoapi core.
No external dependency is needed.  It reads the provider's JSON Schema
(``provider.fields``) and dynamically creates a ``@dataclass`` whose fields match the
data. The type checking is done by ``validate_type`` in ``__post_init__``.

.. code-block:: python

   from dataclasses import dataclass
   from typing import Optional

   from pygeoapi.models.validation import validate_type

   _JSON_SCHEMA_TYPE_MAP = {
       'string': str, 'number': float,
       'integer': int, 'boolean': bool,
   }

   def _make_feature_validator_cls(fields: dict):
       """Build a dataclass validator from provider fields.

       No external dependency required.
       """

       if not fields:
           return None

       annotations = {}
       defaults = {}
       for name, schema in fields.items():
           json_type = schema.get('type', 'string')
           py_type = _JSON_SCHEMA_TYPE_MAP.get(json_type, str)
           annotations[name] = Optional[py_type]
           defaults[name] = None

       ns = {'__annotations__': annotations, **defaults}

       def __post_init__(self):
           validate_type(self)

       ns['__post_init__'] = __post_init__
       cls = type('FeatureValidator', (), ns)
       return dataclass(cls)

This validator catches type errors (e.g. a string where an integer is expected) using
only the standard library.  The provider does not know or define what technology the
validator uses — it only calls ``self._feature_validator(**properties)``.

Injecting a custom validator downstream
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A downstream project, that uses pygeoapi as a library, can subclass ``PluginContext``
and inject a more robust validator.  The provider code does not change, only the
context differs.

The injected validator could be a pydantic ``BaseModel`` with custom field constraints,
a dataclass with ``__post_init__`` validation, or any callable that accepts ``**kwargs``
and raises on invalid input.

.. code-block:: python

   from dataclasses import dataclass
   from typing import Any, Optional

   from pydantic import BaseModel, Field, field_validator
   from pygeoapi.plugin import PluginContext, load_plugin


   @dataclass
   class ValidatingContext(PluginContext):
       """Extended context carrying a feature validator."""
       feature_validator: Optional[Any] = None


   # Stricter validator with domain-specific rules
   class StrictLakeProperties(BaseModel):
       id: int
       scalerank: int = Field(..., ge=0, le=10)
       name: str = Field(..., min_length=1)
       featureclass: str

       @field_validator('featureclass')
       @classmethod
       def must_be_known_class(cls, v):
           allowed = {'Lake', 'Reservoir', 'Playa'}
           if v not in allowed:
               raise ValueError(f'must be one of {allowed}')
           return v


   # Inject via context
   context = ValidatingContext(
       config=provider_def,
       feature_validator=StrictLakeProperties,
   )
   provider = load_plugin('provider', provider_def, context=context)

   # Accepted: valid feature
   provider.create({
       'type': 'Feature',
       'geometry': {'type': 'Point', 'coordinates': [0, 0]},
       'properties': {'id': 1, 'scalerank': 3, 'name': 'Test',
                       'featureclass': 'Lake'},
   })

   # Rejected: scalerank out of range (default validator would accept)
   provider.create({
       'type': 'Feature',
       'geometry': {'type': 'Point', 'coordinates': [0, 0]},
       'properties': {'id': 2, 'scalerank': 99, 'name': 'Test',
                       'featureclass': 'Lake'},
   })

So with the same class in the core and the same data sent to the provider, the result
of the validation may change depending on the injected context.  Without context,
the default validator catches type errors.  With a ``ValidatingContext``, the downstream
project might add domain constraints (value ranges, allowed values, minimum lengths) without
modifying the provider.

Configuration
^^^^^^^^^^^^^

.. code-block:: yaml

   providers:
       - type: feature
         name: pygeoapi.provider.validated_geojson.ValidatedGeoJSONProvider
         data: tests/data/ne_110m_lakes.geojson
         id_field: id
         title_field: name
         editable: true


Featured plugins
----------------

Community based plugins can be found on the `pygeoapi Community Plugins and Themes wiki page`_.


.. _`pygeoapi Community Plugins and Themes wiki page`: https://github.com/geopython/pygeoapi/wiki/CommunityPluginsThemes
.. _`Cookiecutter`: https://github.com/audreyfeldroy/cookiecutter-pypackage
.. _`pygeoapi-plugin-cookiecutter`: https://code.usgs.gov/wma/nhgf/pygeoapi-plugin-cookiecutter
