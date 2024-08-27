
from typing import Dict, List


def create_crs_from_wkt(self: "SpeckleProvider", wkt: str | None) -> None:
    """Create and assign CRS object from WKT string."""

    from pyproj import CRS
    self.crs = CRS.from_user_input(wkt)


def create_crs_from_authid(self: "SpeckleProvider", authid: str | None) -> None:
    """Create and assign CRS object from Authority ID."""

    from pyproj import CRS

    crs_obj = CRS.from_string(authid)
    self.crs = crs_obj

    
def create_crs_default(self: "SpeckleProvider") -> None:
    """Create and assign custom CRS using SpeckleProvider Lat & Lon."""

    from pyproj import CRS

    wkt = f'PROJCS["SpeckleCRS_latlon_{self.lat}_{self.lon}", GEOGCS["GCS_WGS_1984", DATUM["D_WGS_1984", SPHEROID["WGS_1984", 6378137.0, 298.257223563]], PRIMEM["Greenwich", 0.0], UNIT["Degree", 0.0174532925199433]], PROJECTION["Transverse_Mercator"], PARAMETER["False_Easting", 0.0], PARAMETER["False_Northing", 0.0], PARAMETER["Central_Meridian", {self.lon}], PARAMETER["Scale_Factor", 1.0], PARAMETER["Latitude_Of_Origin", {self.lat}], UNIT["Meter", 1.0]]'
    crs_obj = CRS.from_user_input(wkt)
    self.crs = crs_obj
    
def create_crs_dict(self: "SpeckleProvider", offset_x, offset_y, displayUnits: str | None) -> None:
    """Create and assign CRS_dict of SpeckleProvider."""

    if self.crs is not None:
        self.crs_dict = {
            "wkt": self.crs.to_wkt(),
            "offset_x": offset_x,
            "offset_y": offset_y,
            "rotation": self.north_degrees,
            "units_native": displayUnits,
            "obj": self.crs,
        }


def get_set_crs_settings(self: "SpeckleProvider", commit_obj: "Base", context_list: List["TraversalContext"], data: Dict) -> None:
    """Assign CRS object and Dict to SpeckleProvider."""

    from pygeoapi.provider.speckle_utils.display_utils import get_display_units
    from specklepy.objects.GIS.CRS import CRS
    
    assign_coordinate_system_to_geojson(data)

    root_objects = []
    try:
        root_objects = [commit_obj] + commit_obj.elements
    except AttributeError as ex:
        pass # old commit structure

    # iterate Speckle objects to get CRS, DisplayUnits, offsets, rotation
    crs = None
    displayUnits = None
    offset_x = 0
    offset_y = 0

    for item in root_objects:
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
            create_crs_from_wkt(self, crs["wkt"])

            if self.crs.to_authority() is not None:
                data["model_crs"] = f"{self.crs.to_authority()}, {self.crs.name} "
            else:
                data["model_crs"] = f"{self.crs.to_proj4()}"
            break

    # if CRS not found, create default one and get model units for scaling
    if self.crs is None:
        create_crs_default(self)
    if displayUnits is None:
        displayUnits = get_display_units(context_list)

    create_crs_dict(self, offset_x, offset_y, displayUnits)



def assign_coordinate_system_to_geojson(data: Dict):

    crs = {
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        }
    }
    data["crs"] = crs
