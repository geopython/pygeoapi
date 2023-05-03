# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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
import json
import logging
import mimetypes
import os
import re
import functools
from functools import partial
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, IO, Union, List, Callable
from urllib.parse import urlparse
from urllib.request import urlopen

import dateutil.parser
import shapely.ops
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Polygon,
    Point,
    shape as geojson_to_geom,
    mapping as geom_to_geojson,
)
import yaml
from babel.support import Translations
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pyproj
from pyproj.exceptions import CRSError
from requests import Session
from requests.structures import CaseInsensitiveDict

from pygeoapi import __version__
from pygeoapi import l10n
from pygeoapi.models import config as config_models
from pygeoapi.provider.base import ProviderTypeError


LOGGER = logging.getLogger(__name__)

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

TEMPLATES = Path(__file__).parent.resolve() / 'templates'

CRS_AUTHORITY = [
    "AUTO",
    "EPSG",
    "OGC",
]

# Global to compile only once
CRS_URI_PATTERN = re.compile(
    (
     rf"^http://www.opengis\.net/def/crs/"
     rf"(?P<auth>{'|'.join(CRS_AUTHORITY)})/"
     rf"[\d|\.]+?/(?P<code>\w+?)$"
    )
)


# Type for Shapely geometrical objects.
GeomObject = Union[
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
]


@dataclass
class CrsTransformSpec:
    source_crs_uri: str
    source_crs_wkt: str
    target_crs_uri: str
    target_crs_wkt: str


mimetypes.add_type('text/plain', '.yaml')
mimetypes.add_type('text/plain', '.yml')


def dategetter(date_property: str, collection: dict) -> str:
    """
    Attempts to obtain a date value from a collection.

    :param date_property: property representing the date
    :param collection: dictionary to check within

    :returns: `str` (ISO8601) representing the date (allowing
               for an open interval using null)
    """

    value = collection.get(date_property)

    if value is None:
        return None

    return value.isoformat()


def get_typed_value(value: str) -> Union[float, int, str]:
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


def yaml_load(fh: IO) -> dict:
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
            msg = f'Undefined environment variable {env_var} in config'
            raise EnvironmentError(msg)
        return get_typed_value(os.path.expandvars(node.value))

    class EnvVarLoader(yaml.SafeLoader):
        pass

    EnvVarLoader.add_implicit_resolver('!path', path_matcher, None)
    EnvVarLoader.add_constructor('!path', path_constructor)

    return yaml.load(fh, Loader=EnvVarLoader)


def get_api_rules(config: dict) -> config_models.APIRules:
    """ Extracts the default API design rules from the given configuration.

    :param config:  Current pygeoapi configuration (dictionary).
    :returns:       An APIRules instance.
    """
    rules = config['server'].get('api_rules') or {}
    rules.setdefault('api_version', __version__)
    return config_models.APIRules.create(**rules)


def get_base_url(config: dict) -> str:
    """ Returns the full pygeoapi base URL. """
    rules = get_api_rules(config)
    return url_join(config['server']['url'], rules.get_url_prefix())


def str2bool(value: Union[bool, str]) -> bool:
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


def to_json(dict_: dict, pretty: bool = False) -> str:
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

    return json.dumps(dict_, default=json_serial, indent=indent)


def format_datetime(value: str, format_: str = DATETIME_FORMAT) -> str:
    """
    Parse datetime as ISO 8601 string; re-present it in particular format
    for display in HTML

    :param value: `str` of ISO datetime
    :param format_: `str` of datetime format for strftime

    :returns: string
    """

    if not isinstance(value, str) or not value.strip():
        return ''

    return dateutil.parser.isoparse(value).strftime(format_)


def file_modified_iso8601(filepath: Path) -> str:
    """
    Provide a file's ctime in ISO8601

    :param filepath: path to file

    :returns: string of ISO8601
    """

    return datetime.fromtimestamp(
        os.path.getctime(filepath)).strftime('%Y-%m-%dT%H:%M:%SZ')


def human_size(nbytes: int) -> str:
    """
    Provides human readable file size

    source: https://stackoverflow.com/a/14996816

    :param nbytes: int of file size (bytes)
    :param units: list of unit abbreviations

    :returns: string of human readable filesize
    """

    suffixes = ['B', 'K', 'M', 'G', 'T', 'P']

    i = 0

    while nbytes >= 1024 and i < len(suffixes)-1:
        nbytes /= 1024.
        i += 1

    if suffixes[i] == 'K':
        f = str(int(nbytes)).rstrip('0').rstrip('.')
    elif suffixes[i] == 'B':
        return nbytes
    else:
        f = f'{nbytes:.1f}'.rstrip('0').rstrip('.')

    return f'{f}{suffixes[i]}'


def format_duration(start: str, end: str = None) -> str:
    """
    Parse a start and (optional) end datetime as ISO 8601 strings, calculate
    the difference, and return that duration as a string.

    :param start: `str` of ISO datetime
    :param end: `str` of ISO datetime, defaults to `start` for a 0 duration

    :returns: string
    """

    if not isinstance(start, str) or not start.strip():
        return ''
    end = end or start
    duration = dateutil.parser.isoparse(end) - dateutil.parser.isoparse(start)
    return str(duration)


def get_path_basename(urlpath: str) -> str:
    """
    Helper function to derive file basename

    :param urlpath: URL path

    :returns: string of basename of URL path
    """

    return Path(urlpath).name


def json_serial(obj: Any) -> str:
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
    elif type(obj).__name__ == 'int64':
        return int(obj)
    elif type(obj).__name__ == 'float64':
        return float(obj)
    elif isinstance(obj, l10n.Locale):
        return l10n.locale2str(obj)

    msg = f'{obj} type {type(obj)} not serializable'
    LOGGER.error(msg)
    raise TypeError(msg)


def is_url(urlstring: str) -> bool:
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


def render_j2_template(config: dict, template: Path,
                       data: dict, locale_: str = None) -> str:
    """
    render Jinja2 template

    :param config: dict of configuration
    :param template: template (relative path)
    :param data: dict of data
    :param locale_: the requested output Locale

    :returns: string of rendered template
    """

    template_paths = [TEMPLATES, '.']

    locale_dir = config['server'].get('locale_dir', 'locale')
    LOGGER.debug(f'Locale directory: {locale_dir}')

    try:
        templates = config['server']['templates']['path']
        template_paths.insert(0, templates)
        LOGGER.debug(f'using custom templates: {templates}')
    except (KeyError, TypeError):
        LOGGER.debug(f'using default templates: {TEMPLATES}')

    env = Environment(loader=FileSystemLoader(template_paths),
                      extensions=['jinja2.ext.i18n'],
                      autoescape=select_autoescape())

    env.filters['to_json'] = to_json
    env.filters['format_datetime'] = format_datetime
    env.filters['format_duration'] = format_duration
    env.filters['human_size'] = human_size
    env.globals.update(to_json=to_json)

    env.filters['get_path_basename'] = get_path_basename
    env.globals.update(get_path_basename=get_path_basename)

    env.filters['get_breadcrumbs'] = get_breadcrumbs
    env.globals.update(get_breadcrumbs=get_breadcrumbs)

    env.filters['filter_dict_by_key_value'] = filter_dict_by_key_value
    env.globals.update(filter_dict_by_key_value=filter_dict_by_key_value)

    translations = Translations.load(locale_dir, [locale_])
    env.install_gettext_translations(translations)

    template = env.get_template(template)

    return template.render(config=l10n.translate_struct(config, locale_, True),
                           data=data, locale=locale_, version=__version__)


def get_mimetype(filename: str) -> str:
    """
    helper function to return MIME type of a given file

    :param filename: filename (with extension)

    :returns: MIME type of given filename
    """

    return mimetypes.guess_type(filename)[0]


def get_breadcrumbs(urlpath: str) -> list:
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


def filter_dict_by_key_value(dict_: dict, key: str, value: str) -> dict:
    """
    helper function to filter a dict by a dict key

    :param dict_: ``dict``
    :param key: dict key
    :param value: dict key value

    :returns: filtered ``dict``
    """

    return {k: v for (k, v) in dict_.items() if v[key] == value}


def filter_providers_by_type(providers: list, type: str) -> dict:
    """
    helper function to filter a list of providers by type

    :param providers: ``list``
    :param type: str

    :returns: filtered ``dict`` provider
    """

    providers_ = {provider['type']: provider for provider in providers}
    return providers_.get(type)


def get_provider_by_type(providers: list, provider_type: str) -> dict:
    """
    helper function to load a provider by a provider type

    :param providers: ``list`` of providers
    :param provider_type: type of provider (e.g. feature)

    :returns: provider based on type
    """

    LOGGER.debug(f'Searching for provider type {provider_type}')
    try:
        p = (next(d for i, d in enumerate(providers)
                  if d['type'] == provider_type))
    except (RuntimeError, StopIteration):
        raise ProviderTypeError('Invalid provider type requested')

    return p


def get_provider_default(providers: list) -> dict:
    """
    helper function to get a resource's default provider

    :param providers: ``list`` of providers

    :returns: filtered ``dict``
    """

    try:
        default = (next(d for i, d in enumerate(providers) if 'default' in d
                   and d['default']))
        LOGGER.debug('found default provider type')
    except StopIteration:
        LOGGER.debug('no default provider type.  Returning first provider')
        default = providers[0]

    LOGGER.debug(f"Default provider: {default['type']}")
    return default


class ProcessExecutionMode(Enum):
    sync_execute = 'sync-execute'
    async_execute = 'async-execute'


class RequestedProcessExecutionMode(Enum):
    wait = 'wait'
    respond_async = 'respond-async'


class JobStatus(Enum):
    """
    Enum for the job status options specified in the WPS 2.0 specification
    """

    #  From the specification
    accepted = 'accepted'
    running = 'running'
    successful = 'successful'
    failed = 'failed'
    dismissed = 'dismissed'


def read_data(path: Union[Path, str]) -> Union[bytes, str]:
    """
    helper function to read data (file or network)
    """

    LOGGER.debug(f'Attempting to read {path}')

    if isinstance(path, Path) or not path.startswith(('http', 's3')):
        LOGGER.debug('local file on disk')
        with Path(path).open('rb') as fh:
            return fh.read()
    else:
        LOGGER.debug('network file')
        with urlopen(path) as r:
            return r.read()


def url_join(*parts: str) -> str:
    """
    helper function to join a URL from a number of parts/fragments.
    Implemented because urllib.parse.urljoin strips subpaths from
    host urls if they are specified

    Per https://github.com/geopython/pygeoapi/issues/695

    :param parts: list of parts to join

    :returns: str of resulting URL
    """

    return '/'.join([p.strip().strip('/') for p in parts]).rstrip('/')


def get_envelope(coords_list: List[List[float]]) -> list:
    """
    helper function to get the envelope for a given coordinates
    list through the Shapely API.

    :param coords_list: list of coordinates

    :returns: list of the envelope's coordinates
    """

    coords = [tuple(item) for item in coords_list]
    polygon = Polygon(coords)
    bounds = polygon.bounds
    return [[bounds[0], bounds[3]],
            [bounds[2], bounds[1]]]


def get_supported_crs_list(config: dict, default_crs_list: list) -> list:
    """
    Helper function to get a complete list of supported CRSs
    from a (Provider) config dict. Result should always include
    a default CRS according to OAPIF Part 2 OGC Standard.
    This will be the default when no CRS list in config or
    added when (partially) missing in config.

    Author: @justb4

    :param config: dictionary with or without a list of CRSs
    :param default_crs_list: default CRS alternatives, first is default
    :returns: list of supported CRSs
    """
    supported_crs_list = config.get('crs', list())
    contains_default = False
    for uri in supported_crs_list:
        if uri in default_crs_list:
            contains_default = True
            break

    # A default CRS is missing: add the first which is the default
    if not contains_default:
        supported_crs_list.append(default_crs_list[0])
    return supported_crs_list


def get_crs_from_uri(uri: str) -> pyproj.CRS:
    """
    Get a `pyproj.CRS` instance from a CRS URI.
    Author: @MTachon

    :param uri: Uniform resource identifier of the coordinate
        reference system.
    :type uri: str

    :raises `CRSError`: Error raised if no CRS could be identified from the
        URI.

    :returns: `pyproj.CRS` instance matching the input URI.
    :rtype: `pyproj.CRS`
    """

    try:
        crs = pyproj.CRS.from_authority(*CRS_URI_PATTERN.search(uri).groups())
    except CRSError:
        msg = (
            f"CRS could not be identified from URI {uri!r} "
            f"(Authority: {CRS_URI_PATTERN.search(uri).group('auth')!r}, "
            f"Code: {CRS_URI_PATTERN.search(uri).group('code')!r})."
        )
        LOGGER.error(msg)
        raise CRSError(msg)
    except AttributeError:
        msg = (
            f"CRS could not be identified from URI {uri!r}. CRS URIs must "
            "follow the format "
            "'http://www.opengis.net/def/crs/{authority}/{version}/{code}' "
            "(see https://docs.opengeospatial.org/is/18-058r1/18-058r1.html#crs-overview)."  # noqa
        )
        LOGGER.error(msg)
        raise CRSError(msg)
    else:
        return crs


def get_transform_from_crs(
    crs_in: pyproj.CRS, crs_out: pyproj.CRS, always_xy: bool = False
) -> Callable[[GeomObject], GeomObject]:
    """ Get transformation function from two `pyproj.CRS` instances.

    Get function to transform the coordinates of a Shapely geometrical object
    from one coordinate reference system to another.

    :param crs_in: Coordinate Reference System of the input geometrical object.
    :type crs_in: `pyproj.CRS`
    :param crs_out: Coordinate Reference System of the output geometrical
        object.
    :type crs_out: `pyproj.CRS`
    :param always_xy: should axis order be forced to x,y (lon, lat) even if CRS
         declares y,x (lat,lon)
    :type always_xy: `bool`

    :returns: Function to transform the coordinates of a `GeomObject`.
    :rtype: `callable`
    """
    crs_transform = pyproj.Transformer.from_crs(
        crs_in, crs_out, always_xy=always_xy,
    ).transform
    return partial(shapely.ops.transform, crs_transform)


def crs_transform(func):
    """Decorator that transforms the geometry's/geometries' coordinates of a
    Feature/FeatureCollection.

    This function can be used to decorate another function which returns either
    a Feature or a FeatureCollection (GeoJSON-like `dict`). For a
    FeatureCollection, the Features are stored in a ´list´ available at the
    'features' key of the returned `dict`. For each Feature, the geometry is
    available at the 'geometry' key. The decorated function may take a
    'crs_transform_spec' parameter, which accepts a `CrsTransformSpec` instance
    as value. If the `CrsTransformSpec` instance represents a coordinates
    transformation between two different CRSs, the coordinates of the
    Feature's/FeatureCollection's geometry/geometries will be transformed
    before returning the Feature/FeatureCollection. If the 'crs_transform_spec'
    parameter is not given, passed `None` or passed a `CrsTransformSpec`
    instance which does not represent a coordinates transformation, the
    Feature/FeatureCollection is returned unchanged. This decorator can for
    example be use to help supporting coordinates transformation of
    Feature/FeatureCollection `dict` objects returned by the `get` and `query`
    methods of (new or with no native support for transformations) providers of
    type 'feature'.

    :param func: Function to decorate.
    :type func: `callable`

    :returns: Decorated function.
    :rtype: `callable`
    """
    @functools.wraps(func)
    def get_geojsonf(*args, **kwargs):
        crs_transform_spec = kwargs.get('crs_transform_spec')
        result = func(*args, **kwargs)
        if crs_transform_spec is None:
            # No coordinates transformation for feature(s) returned by the
            # decorated function.
            LOGGER.debug('crs_transform: NOT applying coordinate transforms')
            return result
        # Create transformation function and transform the output feature(s)'
        # coordinates before returning them.
        transform_func = get_transform_from_crs(
            pyproj.CRS.from_wkt(crs_transform_spec.source_crs_wkt),
            pyproj.CRS.from_wkt(crs_transform_spec.target_crs_wkt),
        )

        LOGGER.debug(f'crs_transform: transforming features CRS '
                     f'from {crs_transform_spec.source_crs_uri} '
                     f'to {crs_transform_spec.target_crs_uri}')

        features = result.get('features')
        # Decorated function returns a single Feature
        if features is None:
            # Transform the feature's coordinates
            crs_transform_feature(result, transform_func)
        # Decorated function returns a FeatureCollection
        else:
            # Transform all features' coordinates
            for feature in features:
                crs_transform_feature(feature, transform_func)
        return result
    return get_geojsonf


def crs_transform_feature(feature, transform_func):
    """Transform the coordinates of a Feature.

    :param feature: Feature (GeoJSON-like `dict`) to transform.
    :type feature: `dict`
    :param transform_func: Function that transforms the coordinates of a
        `GeomObject` instance.
    :type transform_func: `callable`

    :returns: None
    """
    json_geometry = feature.get('geometry')
    if json_geometry is not None:
        feature['geometry'] = geom_to_geojson(
            transform_func(geojson_to_geom(json_geometry))
        )


def transform_bbox(bbox: list, from_crs: str, to_crs: str) -> list:
    """
    helper function to transform a bounding box (bbox) from
    a source to a target CRS. CRSs in URI str format.
    Uses pyproj Transformer.

    :param bbox: list of coordinates in 'from_crs' projection
    :param from_crs: CRS URI to transform from
    :param to_crs: CRS URI to transform to
    :raises `CRSError`: Error raised if no CRS could be identified from an
        URI.

    :returns: list of 4 or 6 coordinates
    """

    from_crs_obj = get_crs_from_uri(from_crs)
    to_crs_obj = get_crs_from_uri(to_crs)
    transform_func = pyproj.Transformer.from_crs(
        from_crs_obj, to_crs_obj).transform
    n_dims = len(bbox) // 2
    return list(transform_func(*bbox[:n_dims]) + transform_func(
        *bbox[n_dims:]))


class UrlPrefetcher:
    """ Prefetcher to get HTTP headers for specific URLs.
    Allows a maximum of 1 redirect by default.
    """
    def __init__(self):
        self._session = Session()
        self._session.max_redirects = 1

    def get_headers(self, url: str, **kwargs) -> CaseInsensitiveDict:
        """ Issues an HTTP HEAD request to the given URL.
        Returns a case-insensitive dictionary of all headers.
        If the request times out (defaults to 1 second unless `timeout`
        keyword argument is set), or the response has a bad status code,
        an empty dictionary is returned.
        """
        kwargs.setdefault('timeout', 1)
        kwargs.setdefault('allow_redirects', True)
        try:
            response = self._session.head(url, **kwargs)
            response.raise_for_status()
        except Exception:  # noqa
            return CaseInsensitiveDict()
        return response.headers
