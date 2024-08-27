
import math
from typing import Dict, List, Tuple


def convert_point(f_base: "Point", coords, coord_counts):
    """Convert Point."""
    
    coords.append([f_base.x, f_base.y, f_base.z])
    coord_counts.append([1])
    
def convert_line(f_base: "Line", coords, coord_counts):
    """Convert Line."""
    
    start = [f_base.start.x, f_base.start.y, f_base.start.z]
    end = [f_base.end.x, f_base.end.y, f_base.end.z]
    
    coords.extend([start, end])
    coord_counts.append([2])
    
def convert_polyline(f_base: "Polyline", coords, coord_counts):
    """Convert Polyline."""

    coord_counts.append([])
    local_coords = [] # to keep track of just the current polyline
    local_poly_count = 0

    for pt in f_base.as_points():
        coords.append([pt.x, pt.y, pt.z])
        local_coords.append([pt.x, pt.y, pt.z])
        local_poly_count += 1

    # closing point
    if local_poly_count>2 and f_base.closed is True and local_coords[0] != local_coords[-1]:
        coords.append(local_coords[0])
        local_poly_count += 1
    coord_counts[-1].append(local_poly_count)
 
def convert_arc(f_base: "Arc", coords, coord_counts):
    """Convert Arc."""
    
    if f_base.plane is None or f_base.plane.normal.z == 0:
        normal = 1
    else:
        normal = f_base.plane.normal.z
    
    # calculate angles and interval
    interval, angle1, angle2 = getArcRadianAngle(f_base)

    if (angle1 > angle2 and normal == -1) or (angle2 > angle1 and normal == 1):
        pass
    if angle1 > angle2 and normal == 1:
        interval = abs((2 * math.pi - angle1) + angle2)
    if angle2 > angle1 and normal == -1:
        interval = abs((2 * math.pi - angle2) + angle1)

    # set a (random) point density: 24 per 1 rad
    pointsNum = math.floor(abs(interval)) * 24
    if pointsNum < 4:
        pointsNum = 4

    # assign coordinates 
    coord_counts.append([])
    local_poly_count = 0

    for i in range(0, pointsNum + 1):
        k = i / pointsNum  # reset values to fraction
        angle = angle1 + k * interval * normal

        x=f_base.plane.origin.x + f_base.radius * math.cos(angle)
        y=f_base.plane.origin.y + f_base.radius * math.sin(angle)
        z=f_base.plane.origin.z

        coords.append([x, y, z])
        local_poly_count += 1
    coord_counts[-1].append(local_poly_count)

def convert_circle(f_base: "Circle", coords, coord_counts):
    """Convert Circle."""
    
    if f_base.plane is None or f_base.plane.normal.z == 0:
        normal = 1
    else:
        normal = f_base.plane.normal.z
    
    # set a (random) point density: 24 per 1 rad
    interval = 2 * math.pi
    pointsNum = math.floor(abs(interval)) * 24
    if pointsNum < 4:
        pointsNum = 4

    # assign coordinates 
    coord_counts.append([])
    local_poly_count = 0

    for i in range(0, pointsNum + 1):
        k = i / pointsNum  # reset values to fraction
        angle = k * interval * normal

        x=f_base.plane.origin.x + f_base.radius * math.cos(angle)
        y=f_base.plane.origin.y + f_base.radius * math.sin(angle)
        z=f_base.plane.origin.z

        coords.append([x, y, z])
        local_poly_count += 1
    coord_counts[-1].append(local_poly_count)

def convert_polycurve(f_base: "Polycurve", coords, coord_counts):
    """Convert Polycurve."""

    flat_coords = []
    flat_coord_count = [0]

    # put together results from all segment conversions 
    for segm in f_base.segments:
        convert_icurve(segm, coords, coord_counts)
        if len(coord_counts)==0:
            continue
        flat_coords.extend(coords)
        flat_coord_count[-1] += coord_counts[-1][-1]
    
    coords = flat_coords
    coord_counts = flat_coord_count

def convert_curve(f_base: "Curve", coords, coord_counts):
    """Convert Curve using its Polyline displayValue."""

    return convert_polyline(f_base.displayValue, coords, coord_counts)
    
def convert_icurve(f_base: "Base", coords, coord_counts):
    """Convert any ICurve."""
    
    from specklepy.objects.geometry import Line, Polyline, Arc, Curve, Circle, Polycurve, Mesh, Brep
    
    if isinstance(f_base, Line):
        convert_line(f_base, coords, coord_counts)

    elif isinstance(f_base, Polyline):
        convert_polyline(f_base, coords, coord_counts)

    elif isinstance(f_base, Curve):
        convert_curve(f_base, coords, coord_counts)

    elif isinstance(f_base, Arc):
        convert_arc(f_base, coords, coord_counts)

    elif isinstance(f_base, Circle):
        convert_circle(f_base, coords, coord_counts)

    elif isinstance(f_base, Polycurve):
        convert_polycurve(f_base, coords, coord_counts)

def convert_mesh_or_brep(f_base: "Base", coords, coord_counts):
    """Convert Mesh object or Mesh derived from Brep display value."""
    from specklepy.objects.geometry import Mesh, Brep

    faces = []
    vertices = []

    # get faces and vertices
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
    
    # add coordinates
    count: int = 0
    
    for i, pt_count in enumerate(faces):
        if i != count:
            continue

        # old encoding
        if pt_count == 0:
            pt_count = 3
        elif pt_count == 1:
            pt_count = 4

        local_coords_count = [pt_count]
        local_coords = []
        for vertex_index in faces[count + 1 : count + 1 + pt_count]:
            x = vertices[vertex_index * 3]
            y = vertices[vertex_index * 3 + 1]
            z = vertices[vertex_index * 3 + 2]
            local_coords.append([x, y, z])

        count += pt_count + 1
        valid: bool = fix_polygon_orientation(local_coords, True) 
        #if valid:
        coords.extend(local_coords)
        coord_counts.append(local_coords_count)

def convert_polygon(polygon: "Base", coords, coord_counts):
    """Convert GisPolygonGeometry."""
    
    coord_counts.append([])
    
    local_coords_count = 0
    local_coords = []
    for pt in polygon.boundary.as_points():
        local_coords.append([pt.x, pt.y, pt.z])
        local_coords_count += 1

    valid: bool = fix_polygon_orientation(local_coords, True)
    #if valid:
    coords.extend(local_coords)
    coord_counts[-1].append(local_coords_count)

    for void in polygon.voids:
        local_coords_count = 0
        local_coords = []
        for pt_void in void.as_points():
            local_coords.append([pt_void.x, pt_void.y, pt_void.z])
            local_coords_count += 1

        valid: bool = fix_polygon_orientation(local_coords, False)
        #if valid:
        coords.extend(local_coords)
        coord_counts[-1].append(local_coords_count)
    
def convert_hatch(hatch: "Base", coords, coord_counts):
    """Convert Hatch."""
    
    coord_counts.append([])

    loops: list = hatch["loops"]
    boundary = None
    voids = []
    for loop in loops:
        if len(loops)==1 or loop["Type"] == 1: # Outer
            boundary = loop["Curve"]
        else:
            voids.append(loop["Curve"])
    if boundary is None:
        return 

    # record coordinates
    local_coords_count = []
    local_coords = []
    convert_icurve(boundary, local_coords, local_coords_count)
    valid: bool = fix_polygon_orientation(local_coords, True)
    #if valid:
    coords.extend(local_coords)
    coord_counts.extend(local_coords_count)

    for void in voids:
        local_coords_count = []
        local_coords = []
        convert_icurve(void, local_coords, local_coords_count)
        valid: bool = fix_polygon_orientation(local_coords, False)
        #if valid:
        coords.extend(local_coords)
        coord_counts.extend(local_coords_count)

    
def assign_geometry(self: "SpeckleProvider", feature: Dict, f_base) -> Tuple[ List[List[List[float]]], List[List[None| List[int]]] ]:
    """Assign geom type and convert object coords into flat lists of coordinates and schema."""

    from specklepy.objects.geometry import Base, Point, Line, Polyline, Arc, Curve, Circle, Polycurve, Mesh, Brep
    from specklepy.objects.GIS.geometry import GisPolygonGeometry

    geometry = feature["geometry"]
    coords = [] 
    coord_counts = []
    
    if isinstance(f_base, Base) and f_base.speckle_type.endswith("Feature") and len(f_base["geometry"]) > 0: # isinstance(f_base, GisFeature) and len(f_base.geometry) > 0:
        # GisFeature doesn't deserialize properly, need to check for speckle_type 

        if self.requested_data_type == "points" and isinstance(f_base["geometry"][0], Point):
            geometry["type"] = "MultiPoint"
            coord_counts.append(None) # as an indicator of a Multi..type
            
            for geom in f_base["geometry"]:
                convert_point(geom, coords, coord_counts)
            
        elif self.requested_data_type == "lines" and isinstance(f_base["geometry"][0], Polyline):
            geometry["type"] = "MultiLineString"
            coord_counts.append(None)

            for geom in f_base["geometry"]:
                convert_polyline(geom, coords, coord_counts)

        elif self.requested_data_type.startswith("polygons") and isinstance(f_base["geometry"][0], GisPolygonGeometry):
            geometry["type"] = "MultiPolygon"
            coord_counts.append(None)

            for geom in f_base["geometry"]:
                convert_polygon(geom, coords, coord_counts)
    

    elif self.requested_data_type == "points":
        if isinstance(f_base, Point):
            geometry["type"] = "MultiPoint"
            coord_counts.append(None) # as an indicator of a Multi..type
            convert_point(f_base, coords, coord_counts)

        elif isinstance(f_base, Base) and f_base.speckle_type.endswith("PointElement"):
            raise TypeError(f"Deprecated speckleType {f_base.speckle_type}. Try loading more recent data.")
        
    elif self.requested_data_type == "lines":
        if (isinstance(f_base, Line) or 
            isinstance(f_base, Polyline) or 
            isinstance(f_base, Curve) or
            isinstance(f_base, Arc) or
            isinstance(f_base, Circle) or 
            isinstance(f_base, Polycurve)):

            geometry["type"] = "LineString"
            convert_icurve(f_base, coords, coord_counts)
        
        elif isinstance(f_base, Base) and f_base.speckle_type.endswith("LineElement"):
            raise TypeError(f"Deprecated speckleType {f_base.speckle_type}. Try loading more recent data.")
    
    elif self.requested_data_type.startswith("polygons"):
        if isinstance(f_base, Base) and f_base.speckle_type.endswith(".Hatch"):
            geometry["type"] = "MultiPolygon"
            coord_counts.append(None)
            convert_hatch(f_base, coords, coord_counts)

        elif isinstance(f_base, Mesh) or isinstance(f_base, Brep):
            geometry["type"] = "MultiPolygon"        
            coord_counts.append(None) # as an indicator of a Multi..type
            convert_mesh_or_brep(f_base, coords, coord_counts)
        
        elif isinstance(f_base, Base) and f_base.speckle_type.endswith("PolygonElement"):
            raise TypeError(f"Deprecated speckleType {f_base.speckle_type}. Try loading more recent data.")
    
    elif self.requested_data_type == "projectcomments":
        if isinstance(f_base, List): # comment position
            geometry["type"] = "MultiPoint"
            coord_counts.append(None) # as an indicator of a Multi..type

            coords.append([f_base[0], f_base[1], f_base[2]])
            coord_counts.append([1])

    else:
        geometry = {}
        # print(f"Unsupported geometry type: {f_base.speckle_type}")
    
    return coords, coord_counts


def getArcRadianAngle(arc: "Arc") -> List[float]:
    """Calculate start & end angle, and interval of an Arc."""

    interval = None
    normal = arc.plane.normal.z
    angle1, angle2 = getArcAngles(arc)
    if angle1 is None or angle2 is None:
        return None
    interval = abs(angle2 - angle1)

    if (angle1 > angle2 and normal == -1) or (angle2 > angle1 and normal == 1):
        pass
    if angle1 > angle2 and normal == 1:
        interval = abs((2 * math.pi - angle1) + angle2)
    if angle2 > angle1 and normal == -1:
        interval = abs((2 * math.pi - angle2) + angle1)
    return interval, angle1, angle2


def getArcAngles(poly: "Arc") -> Tuple[float | None]:

    if poly.startPoint.x == poly.plane.origin.x:
        angle1 = math.pi / 2
    else:
        angle1 = math.atan(
            abs(
                (poly.startPoint.y - poly.plane.origin.y)
                / (poly.startPoint.x - poly.plane.origin.x)
            )
        )  # between 0 and pi/2

    if (
        poly.plane.origin.x < poly.startPoint.x
        and poly.plane.origin.y > poly.startPoint.y
    ):
        angle1 = 2 * math.pi - angle1
    if (
        poly.plane.origin.x > poly.startPoint.x
        and poly.plane.origin.y > poly.startPoint.y
    ):
        angle1 = math.pi + angle1
    if (
        poly.plane.origin.x > poly.startPoint.x
        and poly.plane.origin.y < poly.startPoint.y
    ):
        angle1 = math.pi - angle1

    if poly.endPoint.x == poly.plane.origin.x:
        angle2 = math.pi / 2
    else:
        angle2 = math.atan(
            abs(
                (poly.endPoint.y - poly.plane.origin.y)
                / (poly.endPoint.x - poly.plane.origin.x)
            )
        )  # between 0 and pi/2

    if (
        poly.plane.origin.x < poly.endPoint.x
        and poly.plane.origin.y > poly.endPoint.y
    ):
        angle2 = 2 * math.pi - angle2
    if (
        poly.plane.origin.x > poly.endPoint.x
        and poly.plane.origin.y > poly.endPoint.y
    ):
        angle2 = math.pi + angle2
    if (
        poly.plane.origin.x > poly.endPoint.x
        and poly.plane.origin.y < poly.endPoint.y
    ):
        angle2 = math.pi - angle2

    return angle1, angle2


def fix_polygon_orientation(
    polygon_pts: List[List[float]], clockwise: bool = True
) -> bool:
    """Changes orientation to clockwise (or counter-) and returns False if polygon has no footprint."""
    
    max_number_of_points = 1000
    coef = int(len(polygon_pts)/max_number_of_points) if len(polygon_pts)>max_number_of_points else 1

    sum_orientation = 0
    for k, _ in enumerate(polygon_pts):
        index = k + 1
        if k == len(polygon_pts) - 1:
            index = 0

        try:
            pt = polygon_pts[k * coef]
            pt2 = polygon_pts[index * coef]

            sum_orientation += (pt2[0] - pt[0]) * (pt2[1] + pt[1])  # if Speckle Points
        except IndexError:
            break

    if clockwise is True and sum_orientation < 0:
        polygon_pts.reverse()
    elif clockwise is False and sum_orientation > 0:
        polygon_pts.reverse()
    
    if sum_orientation ==0:
        return False
    return True

