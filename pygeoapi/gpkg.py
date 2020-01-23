# import gdal
from osgeo import gdal
import json
import logging
from os import remove
from tempfile import NamedTemporaryFile

LOGGER = logging.getLogger(__name__)


def format_handler(**kwargs):
    """
    Handle GeoPackage format and convert GeoJSON to GeoPackage
    with GDAL Python bindings

    :param kwargs: headers_, dataset, content, json_serial

    :returns: tuple of headers, status code, content
    """

    headers_ = kwargs["headers_"]
    dataset = kwargs["dataset"]
    geojson = json.dumps(kwargs["content"], default=kwargs["json_serial"])
    headers_["Content-Type"] = "application/x-sqlite3"
    headers_["Content-Disposition"] = \
        'attachment; filename="{}.gpkg'.format(dataset)
    content = geojson2gpkg(geojson, dataset)
    return headers_, 200, content


def geojson2gpkg(geojson, tablename="items"):
    """
    Convert GeoJSON to GeoPackage content

    :param geojson: string
    :param tablename: string GeoPackage SQLite table name

    :returns: content
    """

    dsi = gdal.OpenEx(geojson)
    layer = dsi.GetLayer()
    tempfile_instance = NamedTemporaryFile("r", suffix="gpkg")
    temp_filename = tempfile_instance.name
    tempfile_instance.close()
    drv = gdal.GetDriverByName("GPKG")
    gpkg_filename = temp_filename + ".gpkg"
    dso = drv.Create(gpkg_filename, 0, 0, 0, gdal.GDT_Unknown)
    dso.CopyLayer(layer, tablename)
    gpkg_file = open(gpkg_filename, "rb")
    content = gpkg_file.read()
    remove(gpkg_filename)
    return content
