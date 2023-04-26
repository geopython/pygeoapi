.. _contributing:

Contributing
============

Building the documentation
--------------------------

To build the documentation in pygeoapi we use `Sphinx`_. The documentation is located in the docs folder.

.. note::
   For the following instructions to work, you must be located in the root folder of pygeoapi.

Install the dependencies necessary for building the documentation using the following command:

.. code-block:: bash

   pip3 install -r docs/requirements-docs.txt

After installing the requirements, build the documentation using the ``sphinx-build`` command:

.. code-block:: bash

   sphinx-build -M html docs/source docs/build


Or using the following ``make`` command:

.. code-block:: bash

   make -C docs html

After building the documentation, the folder ``docs/build`` will contain the website generated with the documentation. 
Add the folder to a web server or open the file ``docs/build/html/index.html`` file in a web browser to see the contents of the documentation.

The documentation is hosted on `readthedocs`_. It is automatically generated from the contents of the ``master`` branch on GitHub.

The file ``.readthedocs.yaml`` contains the configuration of the readthedocs build. Refer to the `readthedocs configuration file`_ documentation for more information.

Contributing GitHub page
------------------------

Please see the `Contributing page <https://github.com/geopython/pygeoapi/blob/master/CONTRIBUTING.md>`_
for information on contributing to the project.

.. _`Sphinx`: https://www.djangoproject.com
.. _`readthedocs`: https://docs.readthedocs.io/en/stable/index.html
.. _readthedocs configuration file: https://docs.readthedocs.io/en/stable/config-file/v2.html