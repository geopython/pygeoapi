.. _developmenrt:

Development
===========

Codebase
--------

The pygeoapi codebase exists at https://github.com/geopython/pygeoapi.

Pull Requests and GitHub Actions
--------------------------------

A given GitHub Pull Request is evaluated against the following GitHub actions:

- main: mainline testing harness (as defined in ``tests``)
- flake8: code linting
- docs: documentation updates (for files updated in ``docs/**.rst``)
- vulnerabilities: Trivy vulnerability scanning

Testing
-------

pygeoapi uses `pytest <https://docs.pytest.org>`_ for managing its automated tests.  Tests
exist in ``/tests`` and are developed for providers, formatters, processes, as well as the
overall API.

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
before committing changes. Pygeoapi's repo includes a ``.pre-commit.yml``
file, check the pre-commit docs on how to set it up - in a nutshell:

- pre-commit is mentioned in pygeoapi's ``requirements-dev.txt`` file, so it will be included
  when you pip install those
- run ``pre-commit install`` once in order to install its git commit hooks.
- optionally, run ``pre-commit run --all-files``, which will run all pre-commit hooks for all files in the repo.
  This also prepares the pre-commit environment.
- from now on, whenever you do a ``git commit``, the pre-commit hooks will run and the commit
  will only be done if all checks pass

Building the documentation
--------------------------

To build the documentation in pygeoapi we use `Sphinx`_. The documentation is located in the docs folder.

.. note::
   For the following instructions to work, you must be located in the root folder of pygeoapi.

Install the dependencies necessary for building the documentation using the following command:

.. code-block:: bash

   pip3 install -r docs/requirements.txt

After installing the requirements, build the documentation using the ``sphinx-build`` command:

.. code-block:: bash

   sphinx-build -M html docs/source docs/build


Or using the following ``make`` command:

.. code-block:: bash

   make -C docs html

After building the documentation, the folder ``docs/build`` will contain the website generated with the documentation. 
Add the folder to a web server or open the file ``docs/build/html/index.html`` file in a web browser to see the contents of the documentation.

The documentation is hosted on `Read the Docs`_. It is automatically generated from the contents of the ``master`` branch on GitHub.

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

   LDFLAGS="-L/usr/local/opt/sqlite/lib -L/usr/local/opt/zlib/lib" CPPFLAGS="-I/usr/local/opt/sqlite/include -I/usr/local/opt/zlib/include" PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions" pyenv install 3.10.12

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
