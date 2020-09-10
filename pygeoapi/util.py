# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2020 Tom Kralidis
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

"""Generic util functions used in the code"""

import base64
from datetime import date, datetime, time
from decimal import Decimal
import json
import logging
import mimetypes
import os
import re
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader
import yaml

from pygeoapi import __version__
from pygeoapi.provider.base import ProviderTypeError

LOGGER = logging.getLogger(__name__)

TEMPLATES = '{}{}templates'.format(os.path.dirname(
    os.path.realpath(__file__)), os.sep)

mimetypes.add_type('text/plain', '.yaml')
mimetypes.add_type('text/plain', '.yml')


def dategetter(date_property, collection):
    """
    Attempts to obtains a date value from a collection.

    :param date_property: property representing the date
    :param collection: dictionary to check within

    :returns: `str` (ISO8601) representing the date. ('..' if null or "now",
        allowing for an open interval).
    """

    value = collection.get(date_property, None)

    if value == 'now' or value is None:
        return '..'

    return value.isoformat()


def get_typed_value(value):
    """
    Derive true type from data value

    :param value: value

    :returns: value as a native Python data type
    """

    try:
        if '.' in value:  # float?
            value2 = float(value)
        elif len(value) > 1 and value.startswith('0'):
            value2 = value
        else:  # int?
            value2 = int(value)
    except ValueError:  # string (default)?
        value2 = value

    return value2


def yaml_load(fh):
    """
    serializes a YAML files into a pyyaml object

    :param fh: file handle

    :returns: `dict` representation of YAML
    """

    # support environment variables in config
    # https://stackoverflow.com/a/55301129
    path_matcher = re.compile(r'.*\$\{([^}^{]+)\}.*')

    def path_constructor(loader, node):
        env_var = path_matcher.match(node.value).group(1)
        if env_var not in os.environ:
            raise EnvironmentError('Undefined environment variable in config')
        return get_typed_value(os.path.expandvars(node.value))

    class EnvVarLoader(yaml.SafeLoader):
        pass

    EnvVarLoader.add_implicit_resolver('!path', path_matcher, None)
    EnvVarLoader.add_constructor('!path', path_constructor)

    return yaml.load(fh, Loader=EnvVarLoader)


def str2bool(value):
    """
    helper function to return Python boolean
    type (source: https://stackoverflow.com/a/715468)

    :param value: value to be evaluated

    :returns: `bool` of whether the value is boolean-ish
    """

    value2 = False

    if isinstance(value, bool):
        value2 = value
    else:
        value2 = value.lower() in ('yes', 'true', 't', '1', 'on')

    return value2


def to_json(dict_, pretty=False):
    """
    Serialize dict to json

    :param dict_: `dict` of JSON representation
    :param pretty: `bool` of whether to prettify JSON (default is `False`)

    :returns: JSON string representation
    """

    if pretty:
        indent = 4
    else:
        indent = None

    return json.dumps(dict_, default=json_serial,
                      indent=indent)


def get_path_basename(urlpath):
    """
    Helper function to derive file basename

    :param urlpath: URL path

    :returns: string of basename of URL path
    """

    return os.path.basename(urlpath)


def json_serial(obj):
    """
    helper function to convert to JSON non-default
    types (source: https://stackoverflow.com/a/22238613)
    :param obj: `object` to be evaluated
    :returns: JSON non-default type to `str`
    """

    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        try:
            LOGGER.debug('Returning as UTF-8 decoded bytes')
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            LOGGER.debug('Returning as base64 encoded JSON object')
            return base64.b64encode(obj)
    elif isinstance(obj, Decimal):
        return float(obj)

    msg = '{} type {} not serializable'.format(obj, type(obj))
    LOGGER.error(msg)
    raise TypeError(msg)


def is_url(urlstring):
    """
    Validation function that determines whether a candidate URL should be
    considered a URI. No remote resource is obtained; this does not check
    the existence of any remote resource.
    :param urlstring: `str` to be evaluated as candidate URL.
    :returns: `bool` of whether the URL looks like a URL.
    """
    try:
        result = urlparse(urlstring)
        return bool(result.scheme and result.netloc)
    except ValueError:
        return False


def render_j2_template(config, template, data):
    """
    render Jinja2 template

    :param config: dict of configuration
    :param template: template (relative path)
    :param data: dict of data

    :returns: string of rendered template
    """

    env = Environment(loader=FileSystemLoader(TEMPLATES))

    env.filters['to_json'] = to_json
    env.globals.update(to_json=to_json)

    env.filters['get_path_basename'] = get_path_basename
    env.globals.update(get_path_basename=get_path_basename)

    env.filters['get_breadcrumbs'] = get_breadcrumbs
    env.globals.update(get_breadcrumbs=get_breadcrumbs)

    env.filters['filter_dict_by_key_value'] = filter_dict_by_key_value
    env.globals.update(filter_dict_by_key_value=filter_dict_by_key_value)

    template = env.get_template(template)
    return template.render(config=config, data=data, version=__version__)


def get_mimetype(filename):
    """
    helper function to return MIME type of a given file

    :param filename: filename (with extension)

    :returns: MIME type of given filename
    """

    return mimetypes.guess_type(filename)[0]


def get_breadcrumbs(urlpath):
    """
    helper function to make breadcrumbs from a URL path

    :param urlpath: URL path

    :returns: `list` of `dict` objects of labels and links
    """

    links = []

    tokens = urlpath.split('/')

    s = ''
    for t in tokens:
        if s:
            s += '/' + t
        else:
            s = t
        links.append({
            'href': s,
            'title': t,
        })

    return links


def filter_dict_by_key_value(dict_, key, value):
    """
    helper function to filter a dict by a dict key

    :param dict_: ``dict``
    :param key: dict key
    :param value: dict key value

    :returns: filtered ``dict``
    """

    return {k: v for (k, v) in dict_.items() if v[key] == value}


def filter_providers_by_type(providers, type):
    """
    helper function to filter a list of providers by type

    :param providers: ``list``
    :param type: str

    :returns: filtered ``dict`` provider
    """

    providers_ = {provider['type']: provider for provider in providers}
    return providers_.get(type, None)


def get_provider_by_type(providers, provider_type):
    """
    helper function to load a provider by a provider type

    :param providers: ``list`` of providers
    :param provider_type: type of provider (feature)

    :returns: provider based on type
    """

    LOGGER.debug('Searching for provider type {}'.format(provider_type))
    try:
        p = (next(d for i, d in enumerate(providers)
                  if d['type'] == provider_type))
    except (RuntimeError, StopIteration):
        raise ProviderTypeError('Invalid provider type requested')

    return p


def get_provider_default(providers):
    """
    helper function to get a resource's default provider

    :param providers: ``list`` of providers

    :returns: filtered ``dict``
    """

    try:
        default = (next(d for i, d in enumerate(providers) if 'default' in d
                   and d['default'] is True))
        LOGGER.debug('found default provider type')
    except StopIteration:
        LOGGER.debug('no default provider type.  Returning first provider')
        default = providers[0]

    LOGGER.debug('Default provider: {}'.format(default['type']))
    return default
