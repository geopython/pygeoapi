.. _plugins:

Plugins
=======

In this section we will explain how pygeoapi uses a plugin approach for data providers, formatters and processes.

Plugin data provider plugin
---------------------------

Plugins are in general modules containing derived classed classes that ensure minimal requirements for the plugin to work.
Lets consider the steps for a data provider plugin (source code is located here: :ref:`data Provider`)

#. create a new module file on the `provider folder` (e.g myprovider.py)
#. copy code from `base.py`
#. import base provider class

   .. code-block:: python
   
      from pygeoapi.provider.base import BaseProvider
   
#. create a child class from the  `BaseProvider` class with a specific name

   .. code-block:: python
   
      class BaseProvider(object):
          """generic Provider ABC"""
      
          def __init__(self, provider_def):
              """
              Initialize object
   
   to become:

   .. code-block:: python
   
      class MyDataProvider(object):
          """My data provider"""
      
         def __init__(self, provider_def):
           """Inherit from parent class"""
           BaseProvider.__init__(self, provider_def)
   


#. implement class methods. 

   .. code-block:: python 
         
         def query(self):
         
         def get(self, identifier):
         
         def create(self, new_feature):
         
         def update(self, identifier, new_feature):
          
         def delete(self, identifier):
   

The above class methods are related to the specific URLs defined on the OGC openapi specification:


.. _processing-plugins:

Processing plugins
------------------

Hi
