# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Just van den Broecke <justb4@gmail.com>
#
# Copyright (c) 2025 Tom Kralidis
# Copyright (c) 2025 Just van den Broecke
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

"""Generic CRS functions used in the code"""

from copy import deepcopy
import functools
from functools import partial
from dataclasses import dataclass
import logging
from typing import Union, Optional, Callable

import pyproj
import pygeofilter.ast
import pygeofilter.values
from pyproj.exceptions import CRSError
from shapely import ops, Geometry
from shapely.geometry import (
    shape as geojson_to_geom,
    mapping as geom_to_geojson
)

LOGGER = logging.getLogger(__name__)

DEFAULT_CRS_LIST = [
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84',
    'http://www.opengis.net/def/crs/OGC/1.3/CRS84h',
]

DEFAULT_CRS = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
DEFAULT_STORAGE_CRS = DEFAULT_CRS


@dataclass
class CrsTransformSpec:
    source_crs_uri: str
    source_crs_wkt: str
    target_crs_uri: str
    target_crs_wkt: str
    always_xy: bool = False


def get_srid(crs: Union[str, pyproj.CRS]) -> Union[int, None]:
    """
    Helper function to attempt to extract an EPSG SRID from
    a `pyproj.CRS` object.

    :param crs: `pyproj.CRS` object

    :returns: int of EPSG SRID, if found
    """
    if isinstance(crs, str):
        crs = get_crs(crs)

    if crs.to_epsg():
        return crs.to_epsg()

    try:
        return pyproj.CRS(crs.to_proj4()).to_epsg()
    except KeyError:
        LOGGER.debug('Unable to extract SRID from proj4 string')


def get_supported_crs_list(
    provider_def: dict, default_crs_list: list = DEFAULT_CRS_LIST
) -> list:
    """
    Helper function to get a complete list of supported CRSs
    from a (Provider) config dict. Result should always include
    a default CRS according to OAPIF Part 2 OGC Standard.
    This will be the default when no CRS list in config or
    added when (partially) missing in config.

    Author: @justb4

    :param provider_def: dictionary with or without a list of CRSs
    :param default_crs_list: default CRS alternatives, first is default

    :returns: list of supported CRSs
    """
    supported_crs_list = provider_def.get('crs', list())
    contains_default = False
    for uri in supported_crs_list:
        if uri in default_crs_list:
            contains_default = True
            break

    # A default CRS is missing: add the first which is the default
    if not contains_default:
        supported_crs_list.append(default_crs_list[0])

    return supported_crs_list


def get_crs(crs: Union[str, pyproj.CRS]) -> pyproj.CRS:
    """
    Get a `pyproj.CRS` instance from a CRS.
    Author: @MTachon

    :param crs: Uniform resource identifier of the coordinate
                reference system. In accordance with
                https://docs.ogc.org/pol/09-048r5.html#_naming_rule
                URIs can take either the form of a URL or a URN
                or `pyproj.CRS` object
    :raises `CRSError`: Error raised if no CRS could be identified from the
        URI.

    :returns: `pyproj.CRS` instance matching the input URI.
    """

    if isinstance(crs, pyproj.CRS):
        return crs

    # normalize the input `uri` to a URL first
    uri = str(crs)
    url = uri.replace(
        'urn:ogc:def:crs', 'http://www.opengis.net/def/crs'
    ).replace(':', '/')
    try:
        authority, code = url.rsplit('/', maxsplit=3)[1::2]
        crs = pyproj.CRS.from_authority(authority, code)
    except ValueError:
        msg = (
            f'CRS could not be identified from URI {uri!r}. CRS URIs must '
            'follow one of two formats: '
            '"http://www.opengis.net/def/crs/{authority}/{version}/{code}" or '
            '"urn:ogc:def:crs:{authority}:{version}:{code}" '
            '(see https://docs.opengeospatial.org/is/18-058r1/18-058r1.html#crs-overview).'  # noqa
        )
        LOGGER.error(msg)
        raise CRSError(msg)
    except CRSError:
        msg = f"CRS could not be identified from URI {uri!r}"
        LOGGER.error(msg)
        raise CRSError(msg)

    return crs


def get_transform_from_spec(
    crs_transform_spec: CrsTransformSpec
) -> Callable[[Geometry], Geometry]:
    """ Get transformation function from a `CrsTransformSpec` instance.

    :param crs_transform_spec: `CrsTransformSpec`

    :returns: `callable` Function to transform the coordinates of a `Geometry`.
    """
    if crs_transform_spec is None:
        LOGGER.warning('No transform spec found')
        return None

    return get_transform_from_crs(
        pyproj.CRS.from_wkt(crs_transform_spec.source_crs_wkt),
        pyproj.CRS.from_wkt(crs_transform_spec.target_crs_wkt),
        crs_transform_spec.always_xy
    )


def get_transform_from_crs(
    crs_in: pyproj.CRS, crs_out: pyproj.CRS, always_xy: bool = False
) -> Callable[[Geometry], Geometry]:
    """ Get transformation function from two `pyproj.CRS` instances.

    Get function to transform the coordinates of a Shapely geometrical object
    from one coordinate reference system to another.

    :param crs_in: `pyproj.CRS` Input Coordinate Reference System
    :param crs_out: `pyproj.CRS` Output Coordinate Reference System
    :param always_xy: 'bool' should axis order be forced to x,y (lon, lat)
                       even if CRSdeclares y,x (lat,lon)

    :returns: `callable` Function to transform the coordinates of a `Geometry`.
    """
    crs_transform = pyproj.Transformer.from_crs(
        crs_in, crs_out, always_xy=always_xy,
    ).transform
    return partial(ops.transform, crs_transform)


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

    :returns: Decorated function.
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
        transform_func = get_transform_from_spec(crs_transform_spec)
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


def crs_transform_feature(feature: dict, transform_func: Callable):
    """Transform the coordinates of a Feature.

    :param feature: Feature (GeoJSON-like `dict`) to transform.
    :param transform_func: Function that transforms the coordinates of a
        `Geometry` instance.

    :returns: None
    """
    json_geometry = feature.get('geometry')
    if json_geometry is not None:
        feature['geometry'] = geom_to_geojson(
            transform_func(geojson_to_geom(json_geometry))
        )


def transform_bbox(bbox: list, from_crs: Union[str, pyproj.CRS],
                   to_crs: Union[str, pyproj.CRS]) -> list:
    """
    helper function to transform a bounding box (bbox) from
    a source to a target CRS. CRSs in URI str format.
    Uses pyproj Transformer.

    :param bbox: list of coordinates in 'from_crs' projection
    :param from_crs: CRS to transform from
    :param to_crs: CRS to transform to
    :raises `CRSError`: Error raised if no CRS could be identified from an
        URI.

    :returns: list of 4 or 6 coordinates
    """

    from_crs_obj = get_crs(from_crs)
    to_crs_obj = get_crs(to_crs)
    transform_func = pyproj.Transformer.from_crs(
        from_crs_obj, to_crs_obj).transform

    n_dims = len(bbox) // 2
    return list(transform_func(*bbox[:n_dims]) + transform_func(
        *bbox[n_dims:]))


def modify_pygeofilter(
    ast_tree: pygeofilter.ast.Node,
    *,
    filter_crs_uri: str,
    storage_crs_uri: Optional[str] = None,
    geometry_column_name: Optional[str] = None
) -> pygeofilter.ast.Node:
    """
    Modifies the input pygeofilter with information from the provider.

    :param ast_tree: `pygeofilter.ast.Node` representing the
                     already parsed pygeofilter expression
    :param filter_crs_uri: URI of the CRS being used in the filtering
                           expression
    :param storage_crs_uri: An optional string containing the URI of
                            the provider's storage CRS
    :param geometry_column_name: An optional string containing the
                                 actual name of the provider's geometry field
    :returns: A new pygeofilter.ast.Node, with the modified filter
              expression

    This function modifies the parsed pygeofilter that contains the raw
    filter expression provided by an external client. It performs the
    following modifications:

    - if the filter includes any spatial coordinates and they are being
      provided in a different CRS from the provider's storage CRS, the
      corresponding geometries are transformed into the storage CRS

    - if the filter includes the generic 'geometry' name as a reference to
      the actual geometry of features, it is replaced by the actual name
      of the geometry field, as specified by the provider

    """
    new_tree = deepcopy(ast_tree)
    if storage_crs_uri:
        _inplace_transform_filter_geometries(
            new_tree, get_crs(filter_crs_uri), get_crs(storage_crs_uri)
        )
    if geometry_column_name:
        _inplace_replace_geometry_filter_name(new_tree, geometry_column_name)
    return new_tree


def _inplace_transform_filter_geometries(
    node: pygeofilter.ast.Node,
    filter_crs: pyproj.CRS,
    storage_crs: pyproj.CRS
) -> None:
    """
    Recursively traverse node tree and convert coordinates to the storage CRS.

    This function modifies nodes in the already-parsed filter in order to find
    any geometry literals that may be used in the filter and, if necessary,
    proceeds to convert spatial coordinates to the CRS used by the provider.
    """
    try:
        sub_nodes = node.get_sub_nodes()
    except AttributeError:
        pass
    else:
        for sub_node in sub_nodes:
            is_geometry_node = isinstance(
                sub_node, pygeofilter.values.Geometry)
            if is_geometry_node:
                # NOTE1: To be flexible, and since pygeofilter
                # already supports it, in addition to supporting
                # the `filter-crs` parameter, we also support having a
                # geometry defined in EWKT, meaning the CRS is provided
                # inline, like this `SRID=<CRS_CODE>;<WKT>` - If provided,
                # this overrides the value of `filter-crs`. This enables
                # supporting, for example, an exotic filter expression with
                # multiple geometries specified in different CRSs

                # NOTE2: We specify a default CRS using a URI of type URN
                # because this is what pygeofilter uses internally too

                crs_urn_provided_in_ewkt = sub_node.geometry.get(
                    'crs', {}).get('properties', {}).get('name')
                if crs_urn_provided_in_ewkt is not None:
                    crs = get_crs(crs_urn_provided_in_ewkt)
                else:
                    crs = filter_crs
                if crs != storage_crs:
                    # convert geometry coordinates to storage crs
                    geom = geojson_to_geom(sub_node.geometry)
                    coord_transformer = pyproj.Transformer.from_crs(
                        crs_from=crs, crs_to=storage_crs).transform
                    transformed_geom = ops.transform(coord_transformer, geom)
                    sub_node.geometry = geom_to_geojson(transformed_geom)
                # ensure the crs is encoded in the sub-node, otherwise
                # pygeofilter will assign it its own default CRS
                authority, code = storage_crs.to_authority()
                sub_node.geometry['crs'] = {
                    'properties': {
                        'name': f'urn:ogc:def:crs:{authority}::{code}'
                    }
                }
            else:
                _inplace_transform_filter_geometries(
                    sub_node, filter_crs, storage_crs)


def _inplace_replace_geometry_filter_name(
    node: pygeofilter.ast.Node,
    geometry_column_name: str
) -> None:
    """Recursively traverse node tree and rename nodes of type ``Attribute``.

    Nodes of type ``Attribute`` named ``geometry`` are renamed to the value of
    the ``geometry_column_name`` parameter.
    """
    try:
        sub_nodes = node.get_sub_nodes()
    except AttributeError:
        pass
    else:
        for sub_node in sub_nodes:
            is_attribute_node = isinstance(sub_node, pygeofilter.ast.Attribute)
            if is_attribute_node and sub_node.name == "geometry":
                sub_node.name = geometry_column_name
            else:
                _inplace_replace_geometry_filter_name(
                    sub_node, geometry_column_name)


def create_crs_transform_spec(
    provider_def: dict, query_crs_uri: Optional[str] = None
) -> Union[None, CrsTransformSpec]:
    """
    Create a `CrsTransformSpec` instance based on provider config and
    *crs* query parameter.

    :param provider_def: Provider config dictionary.
    :param query_crs_uri: Uniform resource identifier of the coordinate
        reference system (CRS) specified in query parameter (if specified).

    :raises ValueError: Error raised if the CRS specified in the query
        parameter is not in the list of supported CRSs of the provider.
    :raises `CRSError`: Error raised if no CRS could be identified from the
        query *crs* parameter (URI).

    :returns: `CrsTransformSpec` instance if the CRS specified in query
        parameter differs from the storage CRS, else `None`.
    """

    # Get storage/default CRS for Collection.
    always_xy = provider_def.get('always_xy', False)
    storage_crs_uri = provider_def.get('storage_crs', DEFAULT_STORAGE_CRS)
    storage_crs = get_crs(storage_crs_uri)

    if not query_crs_uri:
        if storage_crs_uri in DEFAULT_CRS_LIST:
            # Could be that storage_crs is
            # http://www.opengis.net/def/crs/OGC/1.3/CRS84h
            query_crs_uri = storage_crs_uri
        else:
            query_crs_uri = DEFAULT_CRS
        LOGGER.debug(f'no crs parameter, using default: {query_crs_uri}')

    supported_crs_list = get_supported_crs_list(provider_def)
    # Check that the crs specified by the query parameter is supported.
    if query_crs_uri not in supported_crs_list:
        raise ValueError(
            f'CRS {query_crs_uri!r} not supported for this '
            'collection. List of supported CRSs: '
            f'{", ".join(supported_crs_list)}.'
        )
    crs_out = get_crs(query_crs_uri)

    # Check if the crs specified in query parameter differs from the
    # storage crs.
    if storage_crs == crs_out:
        LOGGER.debug('No CRS transformation')
        return None

    LOGGER.debug(
        f'CRS transformation: {storage_crs} -> {crs_out}'
    )
    return CrsTransformSpec(
        source_crs_uri=storage_crs_uri,
        source_crs_wkt=storage_crs.to_wkt(),
        target_crs_uri=query_crs_uri,
        target_crs_wkt=crs_out.to_wkt(),
        always_xy=always_xy
    )


def set_content_crs_header(
    headers: dict, config: dict, query_crs_uri: Optional[str] = None,
) -> None:
    """Set the *Content-Crs* header in responses from providers of Feature
    type.

    :param headers: Response headers dictionary.
    :param config: Provider config dictionary.
    :param query_crs_uri: Uniform resource identifier of the coordinate
        reference system specified in query parameter (if specified).

    :returns: None
    """

    if query_crs_uri:
        content_crs_uri = query_crs_uri
    else:
        # If empty use default CRS
        storage_crs_uri = config.get('storage_crs', DEFAULT_STORAGE_CRS)
        if storage_crs_uri in DEFAULT_CRS_LIST:
            content_crs_uri = storage_crs_uri
        else:
            content_crs_uri = DEFAULT_CRS

    headers['Content-Crs'] = f'<{content_crs_uri}>'
