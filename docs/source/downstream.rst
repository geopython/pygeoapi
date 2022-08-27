.. _downstream:

Downstream Projects 
=======

Downstreaming `pygeoapi` project with various python frameworks.

------------------

In this page, we'll demonstrate how to downstream `pygeoapi` project with various python frameworks.


Django
^^^^^^

Django is a high-level Python web framework that encourages rapid development and clean, pragmatic design. Click `here <https://www.djangoproject.com/>`_ to read more about Django.

In this section we create a sample django project and use `pygeoapi` package as a pluggable django application and serve all the capabilities of `pygeoapi` using Django. For the truly impatient developers, there is a Django `sample_project` in the source code. 

To create everything from scratch please follow these steps : 

- Create a Project folder and create a fresh virtual environment using your preferred tool. e.g.

.. code-block:: bash

   python3 -m venv env

Once created, activate it.

- Install the following dependencies

.. code-block:: bash

   pip install Django pygeoapi

- Create a django project in a directory and cd into it.

.. code-block:: python

   django-admin startproject sampleproject
   cd /sampleproject

-  Download `pygeoapi-config.yml` using 

.. code-block:: bash

   curl -O  https://raw.githubusercontent.com/geopython/pygeoapi/django_pygeoapi/sample_project/pygeoapi-config.yml

and put it in the same folder at root level. 

- Set environment variable

.. code-block:: bash

   export PYGEOAPI_CONFIG=pygeoapi-config.yml
   export PYGEOAPI_OPENAPI=example-openapi.yml

- Run `python manage.py collectstatic` to get all static files. 
- Generate OpenAPI document using following `pygeoapi` command

.. code-block:: bash

   pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI

- Update Django `sampleproject/settings.py` file as per following

.. code-block:: python

   import os
   from pygeoapi.django_app import config

   INSTALLED_APPS = [
   # other apps
   ....
   #pygeoapi app
   'pygeoapi'
   ]

   # Put following setting after STATIC_URL 
   STATIC_ROOT = os.path.join( BASE_DIR / 'assets')

   # Specific pygeoapi setting
   PYGEOAPI_CONFIG = config()
   ...

- Update Django `sampleproject/urls.py` file to run pygeoapi at e.g. `pga` path

.. code-block:: python

   from django.contrib import admin
   from django.urls import path, include 
   from pygeoapi.django_pygeoapi import urls 
   urlpatterns = [
      path('admin/', admin.site.urls),
      path('pga/', include(urls)) # added here
   ]

- Update pygeoapi `pygeoapi-config.yml` file with following settings

1. Update the `url` property under `server` in `pygeoapi-config.yml` accordingly to your django project url. e.g. In this case the path set is `pga` .
2. Update all data paths e.g. `tests/data/ne_110m_lakes.geojson` to match with the absolute path of the pygeoapi project directory.

- Run Django project using `python manage.py runserver`. Once server starts, head over to `localhost:8000/pga` to see `pygeoapi` running.