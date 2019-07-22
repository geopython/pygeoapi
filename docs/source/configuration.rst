.. _configuration:

Configuration
=============

pygeoapi uses a yaml file as configuration source and the file location is read from the ``PYGEOAPI_CONFIG`` env variable

.. note::
   pygeoapi is under high development, and new configuration paramenters are constantely being added. For the lastest parameters
   please consult the `pygeoapi-config.yml <https://github.com/geopython/pygeoapi/blob/master/pygeoapi-config.yml>`_ file provided on github



Using ``pygeoapi-config.yml`` as reference we will have the following sections:

   * `server` for server related configurations
   * `logging` for logging configuration
   * `metadata` server and content metadata (information used to populate multiple content)
   * `datasets` data content offered by server (collections in WFS3.0)

   
   