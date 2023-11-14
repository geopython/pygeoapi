# =================================================================
#
# Authors: Francesco Bartoli <francesco.bartoli@geobeyond.it>
#          Luca Delucchi <lucadeluge@gmail.com>
#          Krishna Lodha <krishnaglodha@gmail.com>
#          Tom Kralidis <tomkralidis@gmail.com>
#          Ricardo Garcia Silva <ricardo.garcia.silva@geobeyond.it>
#
# Copyright (c) 2022 Francesco Bartoli
# Copyright (c) 2022 Luca Delucchi
# Copyright (c) 2022 Krishna Lodha
# Copyright (c) 2022 Tom Kralidis
# Copyright (c) 2023 Ricardo Garcia Silva
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

"""WSGI config for django_ project."""

from pathlib import Path

import django
from django.core.handlers.wsgi import WSGIHandler
from django.conf import global_settings, settings, UserSettingsHolder

import pygeoapi.util
from . import settings as pygeoapi_django_settings


def create_app(
        debug: bool,
        pygeoapi_config_path: str,
        pygeoapi_openapi_path: str
) -> WSGIHandler:
    """Create a WSG application.

    The way that django settings are instantiated follows what is mentioned in
    the django docs':

    https://docs.djangoproject.com/en/4.2/topics/settings/#using-settings-without-setting-django-settings-module

    The django settings are created by strating with the default django global
    settings, then layering the settings specified in the
    `pygeoapi.django_.settings.py` file, and finally overriding the settings
    that depend on values that are gotten from the pygeoapi configuration file.
    """
    pygeoapi_config = pygeoapi.util.get_config_from_path(
        Path(pygeoapi_config_path))
    pygeoapi_openapi_document = pygeoapi.util.get_openapi_from_path(
        Path(pygeoapi_openapi_path))
    api_rules = pygeoapi.util.get_api_rules(pygeoapi_config)
    pygeoapi_django_settings.DEBUG = debug
    pygeoapi_django_settings.PYGEOAPI_CONFIG = pygeoapi_config
    pygeoapi_django_settings.PYGEOAPI_OPENAPI = pygeoapi_openapi_document
    pygeoapi_django_settings.API_RULES = api_rules
    pygeoapi_django_settings.APPEND_SLASH = not api_rules.strict_slashes
    django_settings = UserSettingsHolder(global_settings)
    for attr in dir(pygeoapi_django_settings):
        setattr(django_settings, attr, getattr(pygeoapi_django_settings, attr))
    settings.configure(django_settings)
    django.setup(set_prefix=False)
    return WSGIHandler()

