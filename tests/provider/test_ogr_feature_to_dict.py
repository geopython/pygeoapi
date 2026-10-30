# AI generated code: Junie claude-opus-5-5
"""Tests that the fast OGR feature serializer equals ExportToJson."""

import pytest
from osgeo import ogr

from pygeoapi.provider.ogr import _feature_to_dict


def make_layer(duplicate=False):
    """Create an in-memory OGR layer with various field types."""
    ds = ogr.GetDriverByName('Memory').CreateDataSource('mem')
    layer = ds.CreateLayer('test', geom_type=ogr.wkbPoint)
    layer.CreateField(ogr.FieldDefn('name', ogr.OFTString))
    layer.CreateField(ogr.FieldDefn('count', ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn('value', ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn('date', ogr.OFTDate))
    flag = ogr.FieldDefn('flag', ogr.OFTInteger)
    flag.SetSubType(ogr.OFSTBoolean)
    layer.CreateField(flag)
    if duplicate:
        layer.GetLayerDefn().AddFieldDefn(
            ogr.FieldDefn('name', ogr.OFTString))
    return ds, layer


def assert_parity(feature):
    expected = feature.ExportToJson(as_object=True)
    result = _feature_to_dict(feature)
    assert result == expected
    assert list(result) == list(expected)
    assert list(result['properties']) == list(expected['properties'])
    for key, val in expected['properties'].items():
        assert type(result['properties'][key]) is type(val)
    return result


def test_full_feature():
    ds, layer = make_layer()
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetField('name', 'a')
    feature.SetField('count', 3)
    feature.SetField('value', 1.5)
    feature.SetField('date', '2024/01/02')
    feature.SetField('flag', 1)
    feature.SetGeometry(ogr.CreateGeometryFromWkt('POINT (1 2)'))
    layer.CreateFeature(feature)
    result = assert_parity(layer.GetFeature(feature.GetFID()))
    assert result['properties']['flag'] is True


@pytest.mark.parametrize('flag', [0, None])
def test_boolean_false_and_null(flag):
    ds, layer = make_layer()
    feature = ogr.Feature(layer.GetLayerDefn())
    if flag is None:
        feature.SetFieldNull('flag')
    else:
        feature.SetField('flag', flag)
    layer.CreateFeature(feature)
    result = assert_parity(layer.GetFeature(feature.GetFID()))
    assert result['properties']['flag'] is False


def test_no_geometry_and_no_fid():
    ds, layer = make_layer()
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetField('count', 3)
    result = assert_parity(feature)
    assert result['geometry'] is None
    assert 'id' not in result


def test_duplicate_field_names():
    ds, layer = make_layer(duplicate=True)
    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetField(0, 'first')
    feature.SetField(feature.GetFieldCount() - 1, 'second')
    result = assert_parity(feature)
    assert result['properties']['name'] == 'first'
