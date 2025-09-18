.. _developmenrt:

Development
===========

Codebase
--------

The pygeoapi codebase exists at https://github.com/geopython/pygeoapi.

Pull Requests and GitHub Actions
--------------------------------

A given GitHub Pull Request is evaluated against the following GitHub Actions:

- ``main``: mainline testing harness (as defined in ``tests``)
- ``flake8``: code linting
- ``docs``: documentation updates (for files updated in ``docs/**.rst``)
- ``vulnerabilities``: Trivy vulnerability scanning

Testing
-------

pygeoapi uses `pytest <https://docs.pytest.org>`_ for managing its automated tests.  Tests
exist in ``/tests`` and are developed for providers, formatters, processes, as well as the
overall API.

- API specific tests can be found in ``/tests/api``
- Provider specific tests can be found in ``/tests/provider``
- Manager specific tests can be found in ``/tests/manager``
- Additional/other tests can be found in ``/tests/other``

Tests can be run locally as part of development workflow.  They are also run on pygeoapi’s
`GitHub Actions setup`_ against all commits and pull requests to the code repository.

To run all tests, simply run ``pytest`` in the repository.  To run a specific test file,
run ``pytest tests/api/test_itemtypes.py``, for example.

Some provider tests are subject to external service provisioning and setup (i.e Elasticsearch,
PostgreSQL).  See the `GitHub Action main workflow <https://github.com/geopython/pygeoapi/blob/master/.github/workflows/main.yml>`_
to review the setups taken in order to run provider tests requiring additional infrastructure.

.. _pre-commit:

Linting
-------

pygeoapi follows PEP8 for linting Python source code.  All commits and GitHub Pull Requests
perform ``flake8`` linting compliance prior to approval and/or merge into the codebase.  Running linting
compliance prior to submitting a GitHub Pull Request is recommended.

Using flake8
^^^^^^^^^^^^

Simply running `flake8` against the repository tree will assess the code for linting compliance.

.. note::

   Ensure flake8 is installed (``pip3 install flake8`` or ``pip3 install -r requirements.txt``)

Using pre-commit
^^^^^^^^^^^^^^^^

You may optionally use `pre-commit`_ in order to check for linting and other static issues
before committing changes. pygeoapi's repo includes a ``.pre-commit.yml``
file, check the pre-commit docs on how to set it up - in a nutshell:

- pre-commit is part of ``requirements-dev.txt`` file, so it will be included when installing same
- run ``pre-commit install`` once in order to install its git commit hooks
- optionally, run ``pre-commit run --all-files``, which will run all pre-commit hooks for all files
  in the repository.  Note that this also prepares the pre-commit environment
- When subsequent ``git commit`` commands are run, the pre-commit hooks will run and commit
  on passing checks

Building the documentation
--------------------------

Documentation is managed using `Sphinx`_ and located in the ``docs`` directory.

.. note::
   The following commands should be run from the root folder of the repository.

Install the dependencies necessary for building the documentation using the following command:

.. code-block:: bash

   pip3 install -r docs/requirements.txt

After installing the requirements, build the documentation using the ``sphinx-build`` command:

.. code-block:: bash

   sphinx-build -M html docs/source docs/build


Or using the following ``make`` command:

.. code-block:: bash

   make -C docs/ html

After building the documentation, the ``docs/build`` directory will contain the generated documentation. 

To view the generated documentation locally, use one of the following options:

- run ``python3 -m http.server`` and navigate to ``http://localhost:8000`` in a web browser.  To use a different port, use ``python3 -m http.server 8001``, for example, and navigate to ``http://localhost:8001``
- add the directory to a web server
- open the file ``docs/build/html/index.html`` file in a web browser

The documentation is hosted on `Read the Docs`_ and automatically generated from the contents of the ``master`` branch on GitHub.

The file ``.readthedocs.yaml`` contains the configuration of the Read the Docs build. Refer to the `Read the Docs configuration file`_ documentation for more information.


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

   LDFLAGS="-L/usr/local/opt/sqlite/lib -L/usr/local/opt/zlib/lib" CPPFLAGS="-I/usr/local/opt/sqlite/include -I/usr/local/opt/zlib/include" PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions" pyenv install 3.12.3

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

.. _`flake8`: https://flake8.pycqa.org
.. _`GitHub Actions setup`: https://github.com/geopython/pygeoapi/blob/master/.github/workflows/main.yml
.. _`Sphinx`: https://www.sphinx-doc.org
.. _`Read the Docs`: https://docs.readthedocs.io/en/stable/index.html
.. _`Read the Docs configuration file`: https://docs.readthedocs.io/en/stable/config-file/v2.html
