# =================================================================
#
# Authors: Just van den Broecke <justb4@gmail.com>
#
# Copyright (c) 2023 Just van den Broecke
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

from osgeo import gdal
from osgeo import ogr
from osgeo import osr
import pyproj


def get_spatial_ref(epsg_int, axis_order):
    spatial_ref = osr.SpatialReference()
    spatial_ref.SetAxisMappingStrategy(axis_order)
    spatial_ref.ImportFromEPSG(epsg_int)
    return spatial_ref


def get_axis_order(coords):
    axis_order = 'lat,lon'
    if round(coords[0]) == 5 and round(coords[1]) == 52:
        axis_order = 'lon,lat'
    return axis_order


def test_transforms():
    version_num = int(gdal.VersionInfo('VERSION_NUM'))
    assert version_num > 3000000, f'GDAL version={version_num} must be > 3.0.0'
    print(f'GDAL Version num = {version_num}')

    pyproj.show_versions()
    FORCE_LON_LAT = osr.OAMS_TRADITIONAL_GIS_ORDER
    AUTH_COMPLIANT = osr.OAMS_AUTHORITY_COMPLIANT
    ORDER_LATLON = 'lat,lon'
    ORDER_LONLAT = 'lon,lat'

    CRS_DICT = {
        'http://www.opengis.net/def/crs/OGC/1.3/CRS84':
            {'epsg': 4326, 'order': ORDER_LONLAT, 'mapping': FORCE_LON_LAT}, # noqa
        'http://www.opengis.net/def/crs/EPSG/0/4326':
            {'epsg': 4326, 'order': ORDER_LATLON, 'mapping': AUTH_COMPLIANT}, # noqa
        'http://www.opengis.net/def/crs/EPSG/0/4258':
            {'epsg': 4258, 'order': ORDER_LATLON, 'mapping': AUTH_COMPLIANT}, # noqa
    }

    for crs in CRS_DICT:
        print(f'Testing CRS={crs}')
        crs_entry = CRS_DICT[crs]
        source = get_spatial_ref(28992, AUTH_COMPLIANT)
        target = get_spatial_ref(crs_entry['epsg'], crs_entry['mapping'])

        # Somewhere central in The Netherlands
        x = 130000
        y = 455000

        # Result should be lon = 5.022480 lat = 52.082704
        transformer = osr.CoordinateTransformation(source, target)
        result = transformer.TransformPoint(x, y)

        # Determine Axis order
        axis_order = get_axis_order(result)

        # Axis order should match that of CRS
        print(f'Transform result={result} Axis order={axis_order}')
        crs_axis_order = crs_entry['order']
        assert axis_order == crs_axis_order, f'Axis order for {crs} after Transform should be {crs_axis_order} result={result}' # noqa

        # Create an dummy in-memory OGR dataset
        drv = ogr.GetDriverByName('Memory')
        dst_ds = drv.CreateDataSource('out')
        dst_layer = dst_ds.CreateLayer('dummy', srs=target, geom_type=ogr.wkbPoint) # noqa
        feature_defn = dst_layer.GetLayerDefn()
        feature = ogr.Feature(feature_defn)
        wkt = "POINT({} {})".format(result[0], result[1])
        geom = ogr.CreateGeometryFromWkt(wkt)

        # Suppress swapping by nulling SpatialReference
        geom.AssignSpatialReference(None)
        feature.SetGeometry(geom)
        json_feature = feature.ExportToJson(as_object=True)

        # Determine Axis order after ExportToJson
        coords = json_feature['geometry']['coordinates']
        axis_order = get_axis_order(coords)
        print(f'ExportToJson result={coords} Axis order={axis_order}')
        assert axis_order == crs_axis_order, f'Axis order for {crs} after ExportToJson should be {crs_axis_order} coords={coords}' # noqa


if __name__ == '__main__':
    test_transforms()
