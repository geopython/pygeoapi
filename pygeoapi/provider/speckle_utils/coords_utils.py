
import copy
import math
from typing import List


def reproject_bulk(self, all_coords: List[List[List[float]]], all_coord_counts: List[List[None| List[int]]], geometries) -> None:
    """Reproject coordinates and assign to corresponding geometries."""

    from datetime import datetime

    # reproject all coords
    time1 = datetime.now()
    flat_coords = reproject_2d_coords_list(self, all_coords)
    time2 = datetime.now()
    print(f"Reproject time: {(time2-time1).total_seconds()}")

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
    print(f"Construct back geometry time: {(time3-time2).total_seconds()}")

def reproject_2d_coords_list(self, coords_in: List[List[float]]) -> List[List[float]]:
    """Return coordinates in a CRS of SpeckleProvider."""

    from pyproj import Transformer
    from pyproj import CRS

    coords_offset = offset_rotate(self, copy.deepcopy(coords_in))

    transformer = Transformer.from_crs(
        self.crs,
        CRS.from_user_input(4326),
        always_xy=True,
    )
    transformed = [[pt[0], pt[1], pt[2]] for pt in transformer.itransform(coords_offset)]
    
    all_x = [x[0] for x in transformed]
    all_y = [x[1] for x in transformed]
    self.extent = [min(all_x), min(all_y), max(all_x), max(all_y)]
    return transformed

def offset_rotate(self, coords_in: List[list]) -> List[List[float]]:
    """Apply offset and rotation to coordinates, according to SpeckleProvider CRS_dict."""

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
                scale_factor * (coord[2]),
            ]
        )

    return final_coords
