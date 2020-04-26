.. _install:

Install
=======

pygeoapi is easy to install on numerous environments.  Whether you are a user, administrator or developer, below
are multiple approaches to getting pygeoapi up and running depending on your requirements.

Requirements and dependencies
-----------------------------

pygeoapi runs on Python 3.

Core dependencies are included as part of a given pygeoapi installation procedure.  More specific requirements
details are described below depending on the platform.


For developers and the truly impatient
--------------------------------------

.. code-block:: bash

   python -m venv pygeoapi
   cd pygeoapi
   . bin/activate
   git clone https://github.com/geopython/pygeoapi.git
   cd pygeoapi
   pip install -r requirements.txt
   python setup.py install
   cp pygeoapi-config.yml example-config.yml
   vi example-config.yml
   export PYGEOAPI_CONFIG=example-config.yml
   export PYGEOAPI_OPENAPI=example-openapi.yml
   pygeoapi generate-openapi-document -c $PYGEOAPI_CONFIG > $PYGEOAPI_OPENAPI
   pygeoapi serve
   curl http://localhost:5000


pip
---

`PyPI package info <https://pypi.org/project/pygeoapi>`_

.. code-block:: bash

   pip install pygeoapi

Docker
------

`Docker image <https://hub.docker.com/r/geopython/pygeoapi>`_

.. code-block:: bash

   docker pull geopython/pygeoapi:latest

Conda
-----

`Conda package info <https://anaconda.org/conda-forge/pygeoapi>`_

.. code-block:: bash

   conda install -c conda-forge pygeoapi

UbuntuGIS
---------

`UbuntuGIS package (stable) <https://launchpad.net/%7Eubuntugis/+archive/ubuntu/ppa/+sourcepub/10758317/+listing-archive-extra>`_

`UbuntuGIS package (unstable) <https://launchpad.net/~ubuntugis/+archive/ubuntu/ubuntugis-unstable/+sourcepub/10933910/+listing-archive-extra>`_

.. code-block:: bash

   apt-get install python3-pygeoapi

FreeBSD
-------

`FreeBSD port <https://www.freshports.org/graphics/py-pygeoapi>`_

.. code-block:: bash

   pkg install py-pygeoapi


Summary
-------
Congratulations!  Whichever of the abovementioned methods you chose, you have successfully installed pygeoapi
onto your system.
