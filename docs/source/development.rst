.. _developmenrt:

Development
===========

Codebase
--------

The pygeoapi codebase exists at https://github.com/geopython/pygeoapi.


Testing
-------

pygeoapi uses `pytest <https://docs.pytest.org>`_ for managing its automated tests.  Tests
exist in ``/tests`` and are developed for providers, formatters, processes, as well as the
overall API.

Tests can be run locally as part of development workflow.  They are also run on pygeoapi’s
`GitHub Actions setup`_ against all commits and pull requests to the code repository.

To run all tests, simply run ``pytest`` in the repository.  To run a specific test file,
run ``pytest tests/test_api.py``, for example.


CQL extension lifecycle
-----------------------

Limitations
^^^^^^^^^^^

This workflow is valid only for the `CQL-JSON` format.

Schema
^^^^^^

The Common Query Language (CQL) is the part 3 of the standard OGC API - Features. This extension has its specification available at 
`OGC API - Features - Part 3: Filtering and the Common Query Language (CQL) <https://portal.ogc.org/files/96288>`_ and the schema exists in development at
`cql.json <https://portal.ogc.org/files/96288#cql-json-schema>`_.

Model generation
^^^^^^^^^^^^^^^^

pygeoapi uses a class-based Python model interface to translate the schema into Python objects defined by `pydantic <https://docs.pydantic.dev/>`_ models.
The model is generated with the pre-processing of the schema through the utility ``datamodel-codegen``:

.. code-block:: bash

   # Generate from local downloaded json schema file
   datamodel-codegen  --input ~/Download/cql-schema.json --input-file-type jsonschema --output ./pygeoapi/models/cql_update.py --class-name CQLModel

How to merge
^^^^^^^^^^^^

Once the new pydantic models have been generated then the content of the Python file ``cql_update.py`` can be used to replace the old classes within the ``cql.py`` file.
Update everything above the function ``get_next_node`` and then verify if the tests for the CQL are still passing, for example ``test_post_cql_json_between_query`` 
in ``tests/test_elasticsearch__provider.py``.

Working with Spatialite on OSX
------------------------------

Using pyenv
^^^^^^^^^^^

It is common among OSX developers to use the package manager homebrew for the installation of pyenv to being able to manage multiple versions of Python.
They can encounter errors about the load of some SQLite extensions that pygeoapi uses for handling spatial data formats. In order to run properly the server
you are required to follow these steps below carefully.

Make Homebrew and pyenv play nicely together:

.. code-block:: bash

   # see https://github.com/pyenv/pyenv/issues/106
   alias brew='env PATH=${PATH//$(pyenv root)\/shims:/} brew'


Install Python with the option to enable SQLite extensions:

.. code-block:: bash

   LDFLAGS="-L/usr/local/opt/sqlite/lib -L/usr/local/opt/zlib/lib" CPPFLAGS="-I/usr/local/opt/sqlite/include -I/usr/local/opt/zlib/include" PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions" pyenv install 3.7.6

Configure SQLite from Homebrew over that one shipped with the OS:

.. code-block:: bash

   export PATH="/usr/local/opt/sqlite/bin:$PATH"

Install Spatialite from Homebrew:

.. code-block:: bash

   brew update
   brew install spatialite-tools
   brew libspatialite

Set the variable for the Spatialite library under OSX:

.. code-block:: bash

   SPATIALITE_LIBRARY_PATH=/usr/local/lib/mod_spatialite.dylib


.. _`GitHub Actions setup`: https://github.com/geopython/pygeoapi/blob/master/.github/workflows/main.yml
