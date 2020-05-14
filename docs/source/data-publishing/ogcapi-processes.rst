.. _ogcapi-processes:

Publishing processes via OGC API - Processes
============================================

`OGC API - Processes`_ provides geospatial data processing functionality in a standards-based
fashion (inputs, outputs).

pygeoapi implements OGC API - Processes functionality by providing a plugin architecture, thereby
allowing developers to implement custom processing workflows in Python.

A `sample`_ ``hello-world`` process is provided with the pygeoapi default configuration.

Configuration
-------------

.. code-block:: yaml

   processes:
       hello-world:
           processor:
               name: HelloWorld


Processing examples
-------------------

- list all processes
  - http://localhost:5000/processes
- describe the ``hello-world`` process
  - http://localhost:5000/processes/hello-world


.. todo:: add more examples once OAPIP implementation is complete

.. _`OGC API - Processes`: https://github.com/opengeospatial/wps-rest-binding
.. _`sample`: https://github.com/geopython/pygeoapi/blob/master/pygeoapi/process/hello_world.py
