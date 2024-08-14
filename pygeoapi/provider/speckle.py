# =================================================================
#
# Authors: Matthew Perry <perrygeo@gmail.com>
#
# Copyright (c) 2018 Matthew Perry
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

import copy
import json
import logging
import math
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid

from pygeoapi.provider.base import BaseProvider, ProviderItemNotFoundError
from pygeoapi.util import crs_transform


LOGGER = logging.getLogger(__name__)
_user_data_env_var = "SPECKLE_USERDATA_PATH"
_application_name = "Speckle"
_host_application = "pygeoapi"


class SpeckleProvider(BaseProvider):
    """Provider class for Speckle server data
    This is meant to be simple
    (no external services, no dependencies, no schema)
    at the expense of performance
    (no indexing, full serialization roundtrip on each request)
    Not thread safe, a single server process is assumed
    This implementation uses the feature 'id' heavily
    and will override any 'id' provided in the original data.
    The feature 'properties' will be preserved.
    TODO:
    * query method should take bbox
    * instead of methods returning FeatureCollections,
    we should be yielding Features and aggregating in the view
    * there are strict id semantics; all features in the input GeoJSON file
    must be present and be unique strings. Otherwise it will break.
    * How to raise errors in the provider implementation such that
    * appropriate HTTP responses will be raised
    """

    def __init__(self, provider_def):
        """initializer"""

        super().__init__(provider_def)

        if self.data is None:
            self.data = ""
            # raise ValueError(
            #    "Please provide Speckle project link as an argument, e.g.: 'http://localhost:5000/?limit=100000&https://app.speckle.systems/projects/55a29f3e9d/models/2d497a381d'"
            # )

        from subprocess import run

        # path = str(self.connector_installation_path(_host_application))

        try:
            import specklepy

        except ModuleNotFoundError:
            from pygeoapi.provider.speckle_utils.patch_specklepy import patch_credentials, copy_gis_feature, patch_transport

            completed_process = run(
                [
                    self.get_python_path(),
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "specklepy==2.19.6",
                ],
                capture_output=True,
            )
            completed_process = run(
                [
                    self.get_python_path(),
                    "-m",
                    "pip",
                    "install",
                    "pydantic==1.10.17",
                ],
                capture_output=True,
            )
            patch_credentials()
            copy_gis_feature()
            patch_transport()

            if completed_process.returncode != 0:
                m = f"Failed to install dependenices through pip, got {completed_process.returncode} as return code. Full log: {completed_process}"
                print(m)
                print(completed_process.stdout)
                print(completed_process.stderr)
                raise Exception(m)

        # TODO: replace 1 line in specklepy
        
        # assign global values
        self.url: str = self.data # to store the value and check if self.data has changed
        self.speckle_url = self.url.lower().split("speckleurl=")[-1].split("&")[0].split("@")[0].split("?")[0]

        self.speckle_data = None
        self.model_name = ""

        self.crs = None
        self.crs_dict = None

        self.lat: float = 51.52486388756923
        self.lon: float = 0.1621445437168942
        self.north_degrees: float = 0


    def get_fields(self):
        """
         Get provider field information (names, types)
        :returns: dict of fields
        """

        fields = {}
        LOGGER.debug("Treating all columns as string types")

        if self.speckle_data is None:
            self._load()
            
        # check if the object was extracted
        if isinstance(self.speckle_data, Dict):
            if len(self.speckle_data["features"]) == 0:
                return fields

            for key, value in self.speckle_data["features"][0]["properties"].items():
                if isinstance(value, float):
                    type_ = "number"
                elif isinstance(value, int):
                    type_ = "integer"
                else:
                    type_ = "string"

                fields[key] = {"type": type_}
        return fields

    def _load(self, skip_geometry=None, properties=[], select_properties=[]):
        """Validate Speckle data"""

        if self.data == "":
            return 
            raise ValueError(
                "Please provide Speckle project link as an argument, e.g.: http://localhost:5000/?limit=100000&speckleUrl=https://app.speckle.systems/projects/55a29f3e9d/models/2d497a381d"
            )

        if (
            isinstance(self.data, str)
            and "speckleurl=" in self.data.lower()
            and "projects" in self.data
            and "models" in self.data
        ):
            crs_authid = ""
            for item in self.data.lower().split("&"):

                # if CRS authid is found, rest will be ignored
                if "crsauthid=" in item:
                    crs_authid = item.split("crsauthid=")[1]
                elif "lat=" in item:
                    try:
                        self.lat = float(item.split("lat=")[1])
                    except:
                        pass
                        # raise ValueError(f"Invalid Lat input, must be numeric: {item.split('lat=')[1]}")
                elif "lon=" in item:
                    try:
                        self.lon = float(item.split("lon=")[1])
                    except:
                        pass
                        # raise ValueError(f"Invalid Lon input, must be numeric: {item.split('lon=')[1]}")
                elif "northdegrees=" in item:
                    try:
                        self.north_degrees = float(item.split("northdegrees=")[1])
                    except:
                        pass
                        # raise ValueError(f"Invalid NorthDegrees input, must be numeric: {item.split('northdegrees=')[1]}")

            # if CRS assigned, create one:
            if len(crs_authid)>3:
                self.create_crs_from_authid()

        # check if it's a new request (self.data was updated and doesn't match self.url)
        new_request = False
        if self.url != self.data:
            new_request = True
            self.url = self.data

        # check if self.data was updated OR if features were not created yet
        if (
            new_request is True
            or self.speckle_data is None
            or (
                isinstance(self.speckle_data, dict)
                and hasattr(self.speckle_data, "features")
                and len(self.speckle_data["features"]) > 0
                and not hasattr(self.speckle_data["features"][0], "properties")
            )
        ):
            self.speckle_data = self.load_speckle_data()
            self.fields = self.get_fields()

        # filter by properties if set
        if properties:
            self.speckle_data["features"] = [
                f
                for f in self.speckle_data["features"]
                if all([str(f["properties"][p[0]]) == str(p[1]) for p in properties])
            ]  # noqa

        # All features must have ids, TODO must be unique strings
        if isinstance(self.speckle_data, str):
            raise Exception(self.speckle_data)
        for i in self.speckle_data["features"]:
            # for some reason dictionary is changed to list of links
            try:
                i["properties"]
            except:
                self.speckle_data = None
                return self._load()

            if "id" not in i and self.id_field in i["properties"]:
                i["id"] = i["properties"][self.id_field]
            if skip_geometry:
                i["geometry"] = None
            if self.properties or select_properties:
                i["properties"] = {
                    k: v
                    for k, v in i["properties"].items()
                    if k in set(self.properties) | set(select_properties)
                }  # noqa

        return self.speckle_data

    @crs_transform
    def query(
        self,
        offset=0,
        limit=10,
        resulttype="results",
        bbox=[],
        datetime_=None,
        properties=[],
        sortby=[],
        select_properties=[],
        skip_geometry=False,
        q=None,
        **kwargs,
    ):
        """
        query the provider
        :param offset: starting record to return (default 0)
        :param limit: number of records to return (default 10)
        :param resulttype: return results or hit limit (default results)
        :param bbox: bounding box [minx,miny,maxx,maxy]
        :param datetime_: temporal (datestamp or extent)
        :param properties: list of tuples (name, value)
        :param sortby: list of dicts (property, order)
        :param select_properties: list of property names
        :param skip_geometry: bool of whether to skip geometry (default False)
        :param q: full-text search term(s)
        :returns: FeatureCollection dict of 0..n GeoJSON features
        """

        # TODO filter by bbox without resorting to third-party libs
        data = self._load(
            skip_geometry=skip_geometry,
            properties=properties,
            select_properties=select_properties,
        )
        if data is None:
            return {"features":[]}

        data["numberMatched"] = len(data["features"])

        if resulttype == "hits":
            data["features"] = []
        else:
            data["features"] = data["features"][offset : offset + limit]
            data["numberReturned"] = len(data["features"])

        return data

    @crs_transform
    def get(self, identifier, **kwargs):
        """
        query the provider by id
        :param identifier: feature id
        :returns: dict of single GeoJSON feature
        """

        all_data = self._load()
        # if matches
        for feature in all_data["features"]:
            if str(feature.get("id")) == identifier:
                return feature
        # default, no match
        err = f"item {identifier} not found"
        LOGGER.error(err)
        raise ProviderItemNotFoundError(err)

    def create(self, new_feature):
        """Create a new feature
        :param new_feature: new GeoJSON feature dictionary
        """

        raise NotImplementedError("Creating features is not supported")

    def update(self, identifier, new_feature):
        """Updates an existing feature id with new_feature
        :param identifier: feature id
        :param new_feature: new GeoJSON feature dictionary
        """

        raise NotImplementedError("Updating features is not supported")

    def delete(self, identifier):
        """Deletes an existing feature
        :param identifier: feature id
        """

        raise NotImplementedError("Deleting features is not supported")

    def __repr__(self):
        return f"<SpeckleProvider> {self.data}"

    def load_speckle_data(self: str):
        
        from specklepy.logging.exceptions import SpeckleException
        from specklepy.api import operations
        from specklepy.core.api.wrapper import StreamWrapper
        from specklepy.core.api.client import SpeckleClient
        from specklepy.logging.metrics import set_host_app
        from specklepy.transports.server import ServerTransport

        set_host_app("pygeoapi", "0.0.99")
        
        # get URL that will not trigget Client init
        url_proj: str = self.speckle_url.split("models")[0]
        wrapper: StreamWrapper = StreamWrapper(url_proj)

        # set actual branch
        wrapper.model_id = self.speckle_url.split("models/")[1].split("/")[0].split("&")[0]
        
        # get client by URL, no authentication
        client = SpeckleClient(host=wrapper.host, use_ssl=wrapper.host.startswith("https"))
        client.account.serverInfo.url = url_proj.split("/projects")[0]

        # get branch data
        stream = client.stream.get(
            id = wrapper.stream_id, branch_limit=100
        )

        if isinstance(stream, Exception):
            raise SpeckleException(stream.message+ ", "+ self.speckle_url)

        for br in stream['branches']['items']:
            if br['id'] == wrapper.model_id:
                branch = br
                break

        # set the Model name
        self.model_name = branch['name']
        print(self.model_name)

        commit = branch["commits"]["items"][0]
        objId = commit["referencedObject"]

        transport = ServerTransport(client=client, account=client.account, stream_id=wrapper.stream_id)
        if transport == None:
            raise SpeckleException("Transport not found")

        # data transfer
        try:
            commit_obj = operations.receive(objId, transport, None)
        except Exception as ex:
            # e.g. SpeckleException: Can't get object b53a53697a/f8ce82b242e05eeaab4c6c59fb25e4a0: HTTP error 404 ()
            raise ex

        client.commit.received(
            wrapper.stream_id,
            commit["id"],
            source_application="pygeoapi",
            message="Received commit in pygeoapi",
        )
        print(f"Rendering model '{branch['name']}' of the project '{stream['name']}'")

        speckle_data = self.traverse_data(commit_obj)
        speckle_data["project"] = stream['name']
        speckle_data["model"] = branch['name']

        return speckle_data

    def traverse_data(self, commit_obj):

        from specklepy.objects.geometry import Base
        from specklepy.objects.geometry import Point, Line, Polyline, Curve, Mesh, Brep
        from specklepy.objects.GIS.CRS import CRS
        from specklepy.objects.GIS.geometry import GisPolygonElement
        from specklepy.objects.GIS.GisFeature import GisFeature
        from specklepy.objects.graph_traversal.traversal import (
            GraphTraversal,
            TraversalRule,
        )

        supported_types = [GisFeature, GisPolygonElement, Mesh, Brep, Point, Line, Polyline, Curve]
        # traverse commit
        data: Dict[str, Any] = {
            "type": "FeatureCollection",
            "features": [],
            "model_crs": "-",
        }
        self.assign_crs_to_geojson(data)

        rule = TraversalRule(
            [lambda _: True],
            lambda x: [
                item
                for item in x.get_member_names()
                if isinstance(getattr(x, item, None), list)
                and type(x) not in supported_types
            ],
        )
        context_list = [x for x in GraphTraversal([rule]).traverse(commit_obj)]

        # iterate Speckle objects to get "crs" property
        crs = None
        displayUnits = None
        offset_x = 0
        offset_y = 0
        for item in [commit_obj] + commit_obj.elements:
            if (
                crs is None
                and hasattr(item, "crs")
                and isinstance(item["crs"], CRS)
            ):
                crs = item["crs"]
                displayUnits = crs["units_native"]
                offset_x = crs["offset_x"]
                offset_y = crs["offset_y"]
                self.north_degrees = crs["rotation"]
                self.create_crs_from_wkt(crs["wkt"])

                if self.crs.to_authority() is not None:
                    data["model_crs"] = f"{self.crs.to_authority()}, {self.crs.name} "
                else:
                    data["model_crs"] = f"{self.crs.to_proj4()}"
                break
            elif displayUnits is None and type(item) in supported_types:
                displayUnits = item.units

        # if CRS not found, create default one and get model units for scaling
        if self.crs is None:
            self.create_crs_default()
            for item in context_list:
                if hasattr(item.current, "displayValue"):
                    try:
                        displayVal = item.current["displayValue"]
                    except:
                        displayVal = item.current.displayValue
                    if isinstance(displayVal, list) and len(displayVal)>0:
                        displayUnits = displayVal[0].units
                        break
                    elif isinstance(displayVal, Base):
                        displayUnits = item.current.units
                        break
                else:
                    if item.current.units is not None:
                        displayUnits = item.current.units
                        break

        self.create_crs_dict(offset_x, offset_y, displayUnits)

        # iterate to get features
        list_len = len(context_list)

        load = 0
        print(f"{load}% loaded")

        # get coordinates in bulk
        all_coords = []
        all_coord_counts = []

        for i, item in enumerate(context_list):
            new_load = round(i / list_len * 10, 1) * 10

            if new_load % 10 == 0 and new_load != load:
                load = round(i / list_len * 100)
                print(f"{load}% loaded")

            f_base = item.current
            f_id = item.current.id
            f_fid = len(data["features"]) + 1

            # feature
            feature: Dict = {
                "type": "Feature",
                # "bbox": [-180.0, -90.0, 180.0, 90.0],
                "geometry": {},
                "properties": {
                    "id": f_id,
                    "FID": f_fid,
                    "speckle_type": item.current.speckle_type,
                },
            }

            # feature geometry
            coords, coord_counts = self.assign_geometry(feature, f_base)

            if len(coords)!=0:
                all_coords.extend(coords)
                all_coord_counts.append(coord_counts)

                self.assign_props(f_base, feature["properties"])

                feature["displayProperties"] = {}
                self.assign_color(f_base, feature["displayProperties"])

                # other properties for rendering 
                if isinstance(f_base, Mesh) or isinstance(f_base, Brep):
                    feature["displayProperties"]['lineWidth'] = 0.3
                elif "Line" in feature["geometry"]["type"]: 
                    feature["displayProperties"]['lineWidth'] = 3
                else: 
                    feature["displayProperties"]['lineWidth'] = 1

                # if "Point" in feature["geometry"]["type"]:
                try:
                    feature["displayProperties"]["radius"] = feature["properties"]["weight"]
                except:
                    feature["displayProperties"]["radius"] = 10

                data["features"].append(feature)

        if len(all_coords)==0:
            raise ValueError("No supported features found")

        self.reproject_bulk(all_coords, all_coord_counts, [f["geometry"] for f in data["features"]])

        return data
    
    def reproject_bulk(self, all_coords, all_coord_counts: List[List[None| List[int]]], geometries):
        from datetime import datetime
        # reproject all coords
        time1 = datetime.now()
        flat_coords = self.reproject_2d_coords_list(
            all_coords
        )
        time2 = datetime.now()
        print((time2-time1).total_seconds())

        # define type of features
        feat_coord_group_is_multi = [True if None in x else False for x in all_coord_counts]

        feat_coord_group_counts = [[ y for y in x if y is not None] for x in all_coord_counts]
        feat_coord_group_counts_per_part = [[ sum(y) for y in x if y is not None] for x in all_coord_counts]

        feat_coord_group_flat_counts: List[int] = [sum([ sum(y) for y in x if y is not None]) for x in all_coord_counts]
        
        feat_coord_groups = [flat_coords[sum(feat_coord_group_flat_counts[:i]):sum(feat_coord_group_flat_counts[:i])+x] for i, x in enumerate(feat_coord_group_flat_counts)]

        for i, geometry in enumerate(geometries):
            geometry["coordinates"] = []
            if feat_coord_group_is_multi[i] is False:
                
                if geometry["type"] == "Point":
                    geometry["coordinates"].extend(feat_coord_groups[i][0])
                else:
                    geometry["coordinates"].extend(feat_coord_groups[i])
            else:
                polygon_parts = []
                local_coords_count: List[List[int]] = feat_coord_group_counts[i]
                local_coords_count_flat: List[int] = feat_coord_group_counts_per_part[i]
                local_flat_coords: List[int] = feat_coord_groups[i]

                for c, poly_part_count_lists in enumerate(local_coords_count):
                    poly_part = []
                    start_index = sum(local_coords_count_flat[:c]) if c!=0 else 0 # all used coords in all parts

                    for part_count in poly_part_count_lists:
                        range_coords_indices = range(start_index, start_index + part_count)
                        
                        if geometry["type"] == "MultiPoint":
                            poly_part.extend([local_flat_coords[ind] for ind in range_coords_indices])
                        else:
                            poly_part.append([local_flat_coords[ind] for ind in range_coords_indices])

                        start_index += part_count
                    
                    if geometry["type"] in ["MultiPoint","MultiLineString"] :
                        polygon_parts.extend(poly_part)
                    else:
                        polygon_parts.append(poly_part)

                geometry["coordinates"].extend(polygon_parts)
        
        time3 = datetime.now()
        print((time3-time2).total_seconds())

    def create_crs_from_wkt(self, wkt: str | None):

        from pyproj import CRS
        self.crs = CRS.from_user_input(wkt)

    def create_crs_from_authid(self, authid: str | None):

        from pyproj import CRS

        crs_obj = CRS.from_string(authid)
        self.crs = crs_obj

    def create_crs_default(self):

        from pyproj import CRS

        wkt = f'PROJCS["SpeckleCRS_latlon_{self.lat}_{self.lon}", GEOGCS["GCS_WGS_1984", DATUM["D_WGS_1984", SPHEROID["WGS_1984", 6378137.0, 298.257223563]], PRIMEM["Greenwich", 0.0], UNIT["Degree", 0.0174532925199433]], PROJECTION["Transverse_Mercator"], PARAMETER["False_Easting", 0.0], PARAMETER["False_Northing", 0.0], PARAMETER["Central_Meridian", {self.lon}], PARAMETER["Scale_Factor", 1.0], PARAMETER["Latitude_Of_Origin", {self.lat}], UNIT["Meter", 1.0]]'
        crs_obj = CRS.from_user_input(wkt)
        self.crs = crs_obj

    def create_crs_dict(self, offset_x, offset_y, displayUnits: str | None):
        if self.crs is not None:
            self.crs_dict = {
                "wkt": self.crs.to_wkt(),
                "offset_x": offset_x,
                "offset_y": offset_y,
                "rotation": self.north_degrees,
                "units_native": displayUnits,
                "obj": self.crs,
            }

    def assign_geometry(self, feature: Dict, f_base):

        from specklepy.objects.geometry import Point, Line, Polyline, Curve, Mesh, Brep
        from specklepy.objects.GIS.geometry import GisPolygonGeometry
        from specklepy.objects.GIS.GisFeature import GisFeature

        geometry = feature["geometry"]
        coords = [] 
        coord_counts = []

        if isinstance(f_base, Point):
            geometry["type"] = "MultiPoint"
            coord_counts.append(None)

            coords.append([f_base.x, f_base.y])
            coord_counts.append([1])

        elif isinstance(f_base, Mesh) or isinstance(f_base, Brep):
            geometry["type"] = "MultiPolygon"
            coord_counts.append(None) # as an indicator of a MultiPolygon

            faces = []
            vertices = []
            if isinstance(f_base, Mesh):
                faces = f_base.faces
                vertices = f_base.vertices
            elif isinstance(f_base, Brep):
                if f_base.displayValue is None or (
                    isinstance(f_base.displayValue, list)
                    and len(f_base.displayValue) == 0
                ):
                    geometry = {}
                    return
                elif isinstance(f_base.displayValue, list):
                    faces = f_base.displayValue[0].faces
                    vertices = f_base.displayValue[0].vertices
                else:
                    faces = f_base.displayValue.faces
                    vertices = f_base.displayValue.vertices

            count: int = 0
            for i, pt_count in enumerate(faces):
                if i != count:
                    continue

                # old encoding
                if pt_count == 0:
                    pt_count = 3
                elif pt_count == 1:
                    pt_count = 4
                coord_counts.append([pt_count])

                for vertex_index in faces[count + 1 : count + 1 + pt_count]:
                    x = vertices[vertex_index * 3]
                    y = vertices[vertex_index * 3 + 1]
                    coords.append([x, y])

                count += pt_count + 1

        elif isinstance(f_base, GisFeature) and len(f_base.geometry) > 0:
            
            if isinstance(f_base.geometry[0], Point):
                geometry["type"] = "MultiPoint"
                coord_counts.append(None)
                
                for geom in f_base.geometry:
                    coords.append([geom.x, geom.y])
                    coord_counts.append([1])
                
            elif isinstance(f_base.geometry[0], Polyline):
                geometry["type"] = "MultiLineString"
                coord_counts.append(None)

                for geom in f_base.geometry:
                    coord_counts.append([])
                    local_poly_count = 0

                    for pt in geom.as_points():
                        coords.append([pt.x, pt.y])
                        local_poly_count += 1
                    if len(coords)>2 and geom.closed is True and coords[0] != coords[-1]:
                        coords.append(coords[0])
                        local_poly_count += 1

                    coord_counts[-1].append(local_poly_count)

            elif isinstance(f_base.geometry[0], GisPolygonGeometry):
                geometry["type"] = "MultiPolygon"
                coord_counts.append(None)

                for polygon in f_base.geometry:
                    coord_counts.append([])
                    boundary_count = 0
                    for pt in polygon.boundary.as_points():
                        coords.append([pt.x, pt.y])
                        boundary_count += 1
                    
                    coord_counts[-1].append(boundary_count)

                    for void in polygon.voids:
                        void_count = 0
                        for pt_void in void.as_points():
                            coords.append([pt_void.x, pt_void.y])
                            void_count += 1
                        
                        coord_counts[-1].append(void_count)

        elif isinstance(f_base, Line):
            geometry["type"] = "LineString"
            start = [f_base.start.x, f_base.start.y]
            end = [f_base.end.x, f_base.end.y]
            
            coords.extend([start, end])
            coord_counts.append([2])

        elif isinstance(f_base, Polyline):
            geometry["type"] = "LineString"
            for pt in f_base.as_points():
                coords.append([pt.x, pt.y])
            if len(coords)>2 and f_base.closed is True and coords[0] != coords[-1]:
                coords.append(coords[0])
                
            coord_counts.append([len(coords)])

        elif isinstance(f_base, Curve):
            geometry["type"] = "LineString"
            #geometry["coordinates"] = []
            for pt in f_base.displayValue.as_points():
                #geometry["coordinates"].append([pt.x, pt.y])
                coords.append([pt.x, pt.y])
            if len(coords)>2 and f_base.displayValue.closed is True and coords[0] != coords[-1]:
                coords.append(coords[0])

            coord_counts.append([len(coords)])
            #geometry["coordinates"] = self.reproject_2d_coords_list(
            #    geometry["coordinates"]
            #)

        else:
            geometry = {}
            # print(f"Unsupported geometry type: {f_base.speckle_type}")
        
        return coords, coord_counts

    def reproject_2d_coords_list(self, coords_in: List[list]):

        from pyproj import Transformer
        from pyproj import CRS

        coords_offset = self.offset_rotate(copy.deepcopy(coords_in))

        transformer = Transformer.from_crs(
            self.crs,
            CRS.from_user_input(4326),
            always_xy=True,
        )
        return [[pt[0], pt[1]] for pt in transformer.itransform(coords_offset)]

    def offset_rotate(self, coords_in: List[list]):

        from specklepy.objects.units import get_scale_factor_from_string

        scale_factor = 1
        if isinstance(self.crs_dict["units_native"], str):
            scale_factor = get_scale_factor_from_string(self.crs_dict["units_native"], "m")

        final_coords = []
        for coord in coords_in:
            a = self.crs_dict["rotation"] * math.pi / 180
            x2 = coord[0] * math.cos(a) - coord[1] * math.sin(a)
            y2 = coord[0] * math.sin(a) + coord[1] * math.cos(a)
            final_coords.append(
                [
                    scale_factor * (x2 + self.crs_dict["offset_x"]),
                    scale_factor * (y2 + self.crs_dict["offset_y"]),
                ]
            )

        return final_coords

    def assign_crs_to_geojson(self, data: Dict):

        crs = {
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
            }
        }

        data["crs"] = crs

    def assign_props(self, obj, props):
        from specklepy.objects.geometry import Base

        all_prop_names = obj.get_member_names()

        # check if GIS object
        if "attributes" in all_prop_names and isinstance(obj["attributes"], Base):
            all_prop_names = obj["attributes"].get_member_names()

            for prop_name in all_prop_names:

                value = getattr(obj["attributes"], prop_name)

                if (prop_name
                    in [
                        "geometry",
                        "speckle_type",
                        "totalChildrenCount",
                        "units",
                        "applicationId",
                        "Speckle_ID",
                        "id",
                    ]
                ):
                    pass
                else:
                    if (
                    isinstance(value, Base)
                    or isinstance(value, List)
                    or isinstance(value, Dict)
                    ):
                        props[prop_name] = str(value)
                    else:
                        props[prop_name] = value
            return 
        
        # if not GIS: 
        for prop_name in obj.get_member_names():
            if (
                prop_name
                in [
                    "x",
                    "y",
                    "z",
                    "geometry",
                    "speckle_type",
                    "totalChildrenCount",
                    "vertices",
                    "faces",
                    "colors",
                    "bbox",
                    "value",
                    "domain",
                    "displayValue",
                    "displayStyle",
                    "textureCoordinates",
                    "renderMaterial",
                    "applicationId",
                    "TrimsValue",
                    "LoopsValue",
                    "Faces",
                    "VerticesValue",
                    "EdgesValue",
                    "Curve2DValues",
                    "Vertices",
                    "Loops",
                    "Curve3D",
                    "FacesValue",
                    "SurfacesValue",
                    "Edges",
                    "Surfaces",
                    "Curve3DValues",
                    "Trims",
                    "Curve2D",
                ]
            ):
                pass
            else:
                value = getattr(obj, prop_name)
                if (
                    isinstance(value, Base)
                    or isinstance(value, List)
                    or isinstance(value, Dict)
                ):
                    props[prop_name] = str(value)
                else:
                    props[prop_name] = value

    def find_display_obj(self, obj):

        from specklepy.objects.geometry import Base

        if hasattr(obj, 'displayValue'):
            displayVal = obj.displayValue
            if isinstance(displayVal, List):
                for item in displayVal:
                    return item
            
            if isinstance(displayVal, Base):
                return displayVal
        return obj

    def assign_color(self, obj, props):
        from specklepy.objects.geometry import Base, Mesh

        # initialize Speckle Blue color
        color = (255 << 24) + (10 << 16) + (132 << 8) + 255

        # find color property
        obj_display = self.find_display_obj(obj)

        try:
            if hasattr(obj_display, 'renderMaterial'):
                color = obj_display['renderMaterial']['diffuse']
            elif hasattr(obj_display, '@renderMaterial'):
                color = obj_display['@renderMaterial']['diffuse']
            elif hasattr(obj_display, 'displayStyle'):
                color = obj_display['displayStyle']['color']
            elif hasattr(obj_display, '@displayStyle'):
                color = obj_display['@displayStyle']['color']
            elif isinstance(obj_display, Mesh) and isinstance(obj_display.colors, List):
                sameColors = True
                color1 = obj_display.colors[0]
                for c in obj_display.colors:
                    if c != color1:
                        sameColors = False
                        break
                if sameColors is True:
                    color = color1
        except Exception as e:
            print(e)
        
        r, g, b = self.get_r_g_b(color)
        hex_color = '#%02x%02x%02x' % (r, g, b)
        props['color'] = hex_color

    def get_r_g_b(self, rgb: int) -> Tuple[int, int, int]:
        r = g = b = 0
        try:
            r = (rgb & 0xFF0000) >> 16
            g = (rgb & 0xFF00) >> 8
            b = rgb & 0xFF
        except Exception as e:
            r = g = b = 150
        return r, g, b


    def get_python_path(self):
        if sys.platform.startswith("linux"):
            return sys.executable
        pythonExec = os.path.dirname(sys.executable)
        if sys.platform == "win32":
            pythonExec += "\\python"
        else:
            pythonExec += "/bin/python3"
        return pythonExec

    def user_application_data_path(self) -> "Path":
        """Get the platform specific user configuration folder path"""
        from pathlib import Path

        path_override = self._path()
        if path_override:
            return path_override

        try:
            if sys.platform.startswith("win"):
                app_data_path = os.getenv("APPDATA")
                if not app_data_path:
                    raise Exception("Cannot get appdata path from environment.")
                return Path(app_data_path)
            else:
                # try getting the standard XDG_DATA_HOME value
                # as that is used as an override
                app_data_path = os.getenv("XDG_DATA_HOME")
                if app_data_path:
                    return Path(app_data_path)
                else:
                    return self.ensure_folder_exists(Path.home(), ".config")
        except Exception as ex:
            raise Exception("Failed to initialize user application data path.", ex)

    def ensure_folder_exists(self, base_path: "Path", folder_name: str) -> "Path":
        from pathlib import Path

        path = base_path.joinpath(folder_name)
        path.mkdir(exist_ok=True, parents=True)
        return path

    def _path(self) -> Optional["Path"]:
        from pathlib import Path

        """Read the user data path override setting."""
        path_override = os.environ.get(_user_data_env_var)
        if path_override:
            return Path(path_override)
        return None

    def connector_installation_path(self, host_application: str) -> "Path":
        connector_installation_path = self.user_speckle_connector_installation_path(
            host_application
        )
        connector_installation_path.mkdir(exist_ok=True, parents=True)

        # set user modules path at beginning of paths for earlier hit
        if sys.path[0] != connector_installation_path:
            sys.path.insert(0, str(connector_installation_path))

        # print(f"Using connector installation path {connector_installation_path}")
        return connector_installation_path

    def user_speckle_connector_installation_path(self, host_application: str) -> "Path":
        """
        Gets a connector specific installation folder.
        In this folder we can put our connector installation and all python packages.
        """
        return self.ensure_folder_exists(
            self.ensure_folder_exists(
                self.user_speckle_folder_path(), "connector_installations"
            ),
            host_application,
        )

    def user_speckle_folder_path(self) -> "Path":
        """Get the folder where the user's Speckle data should be stored."""
        return self.ensure_folder_exists(
            self.user_application_data_path(), _application_name
        )
