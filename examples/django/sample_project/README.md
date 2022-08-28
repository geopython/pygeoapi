# pygeoapi Django integration

This directory contains a [sample Django project](https://djangoproject.com) demonstrating how to
integrate pygeoapi into your Django application.

Django is a Python web framework that encourages rapid development and clean, pragmatic design.

In this document we create a sample Django project and use pygeoapi as a pluggable, embedded application.

To create your Django application from scratch follow these steps: 

```bash

# create a project directory and create a fresh virtual environment
python3 -m venv env
cd env
source bin/activate

# install dependencies
pip install Django pygeoapi

# create a Django project
django-admin startproject sampleproject
cd sampleproject

# set pygeoapi environment variables
export PYGEOAPI_CONFIG=`pwd`/pygeoapi-config.yml
export PYGEOAPI_OPENAPI=`pwd`/example-openapi.yml

# Django: collect all static assets/files
python3 manage.py collectstatic

# generate OpenAPI document
pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI
```

Update `settings.py`:

```python

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
```

Update `urls.py` to run pygeoapi at e.g. `pga` path

```python

from django.contrib import admin
from django.urls import path, include 
from pygeoapi.django_pygeoapi import urls 
urlpatterns = [
    path('admin/', admin.site.urls),
    path('pga/', include(urls)) # added here
]
```

Update `pygeoapi-config.yml` as follows:

- set the `server.url` property according to your Django application URL (e.g. in this case the path set is `pga`)
- set all data paths (e.g. `tests/data/ne_110m_lakes.geojson`) to match with the absolute path of the project directory

Finally, run your Django project:

```bash
python3 manage.py runserver`. Once server starts, head over to `localhost:8000/pga` to see `pygeoapi` running.
```

At this point you can go your Django / pygeoapi project at `http://localhost:8000/pga` 
