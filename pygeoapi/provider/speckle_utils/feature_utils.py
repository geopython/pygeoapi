
from datetime import datetime
from typing import Dict, List


def initialize_features(self: "SpeckleProvider", all_coords, all_coord_counts, data, context_list, comments: Dict) -> None:
    """Create features with props and displayProps, and assign flat list of coordinates."""

    from pygeoapi.provider.speckle_utils.props_utils import assign_props, assign_missing_props
    from pygeoapi.provider.speckle_utils.converter_utils import assign_geometry
    from pygeoapi.provider.speckle_utils.display_utils import find_display_obj, assign_display_properties, find_list_of_display_obj

    print(f"Creating features..")
    time1 = datetime.now()
    
    all_props = []

    if self.requested_data_type != "projectcomments":
        for item in context_list:
            
            f_base = item.current
            f_id = item.current.id
            f_fid = len(data["features"]) + 1

            # initialize feature
            feature: Dict = {
                "type": "Feature",
                # "bbox": [-180.0, -90.0, 180.0, 90.0],
                "geometry": {},
                "displayProperties":{
                    "object_type": "geometry",
                },
                "properties": {
                    "id": f_id,
                    "FID": f_fid,
                    "speckle_type": item.current.speckle_type.split(":")[-1],
                },
            }

            # feature geometry, props and displayProps
            coords = []
            coord_counts = []

            if "true" in self.preserve_attributes:
                obj_display, obj_get_color = find_display_obj(f_base)

                try: # don't break the code if 1 feature fails
                    coords, coord_counts = assign_geometry(self, feature, obj_display)
                except TypeError as ex:
                    raise ex
                except Exception as e:
                    print(e)
                    pass

                if len(coords)!=0:
                    all_coords.extend(coords)
                    all_coord_counts.append(coord_counts)
                    
                    assign_props(f_base, feature["properties"])
                    # update list of all properties
                    for prop in feature["properties"]:
                        if prop not in all_props:
                            all_props.append(prop)
                    
                    assign_display_properties(feature, f_base,  obj_get_color)
                    feature["max_height"] = max([c[2] for c in coords])
                    data["features"].append(feature)
                
            else:
                list_of_display_obj = find_list_of_display_obj(f_base)
                
                for k, vals in enumerate(list_of_display_obj):
                    obj_display, obj_get_color = vals
                    
                    f_fid = len(data["features"]) + 1
                    feature_new: Dict = {
                        "type": "Feature",
                        # "bbox": [-180.0, -90.0, 180.0, 90.0],
                        "geometry": {},
                        "displayProperties":{
                            "object_type": "geometry",
                        },
                        "properties": {
                            "id": f_id + "_" + str(k),
                            "FID": f_fid,
                            "speckle_type": item.current.speckle_type.split(":")[-1],
                        },
                    }
                    coords = []
                    coord_counts = []
                    
                    try: # don't break the code if 1 feature fails
                        coords, coord_counts = assign_geometry(self, feature_new, obj_display)
                    except TypeError as ex:
                        raise ex
                    except Exception as e:
                        print(e)
                        pass

                    if len(coords)!=0:
                        all_coords.extend(coords)
                        all_coord_counts.append(coord_counts)

                        assign_display_properties(feature_new, f_base,  obj_get_color)
                        feature_new["max_height"] = max([c[2] for c in coords])
                        data["features"].append(feature_new)
  
        assign_missing_props(data["features"], all_props)
    else:
        ####################### create comment features
        for comm_id, comment in comments.items():
            # initialize comment
            feature: Dict = {
                "type": "Feature",
                "id": comm_id,
                "geometry": {},
                "displayProperties": {
                    "object_type": "comment",
                },
                "properties": {
                    "messages": [],
                    "text_html": "",
                    "resource_id": "",
                    "all_attachments": []
                },
            }

            coords = []
            coord_counts = []
            try: # don't break the code if 1 comment fails
                coords, coord_counts = assign_geometry(self, feature, comment["position"])
            except Exception as e:
                print(e)
                pass
            
            if len(coords)!=0:
                all_coords.extend(coords)
                all_coord_counts.append(coord_counts)
                assign_comment_data(comment["items"], feature["properties"])
                data["comments"].append(feature)
        ########################

    if len(data["features"])==0 and len(data["comments"])==0:
        raise ValueError("No supported features found")
    
    time2 = datetime.now()
    print(f"Creating features time: {(time2-time1).total_seconds()}")

def assign_comment_data(comments, properties):
    """Create html text to display for the thread."""
    
    for item in comments:
        r'''
        "author": author_name,
        "date": created_date, # e.g. 2024-08-25T13:52:50.562Z
        "text": raw_text,
        "attachments": [attachments_paths],
        "resource_id": string
        '''
        try:
            formatted_time = datetime.strptime(item["date"].replace("T", " ").replace("Z","").split(".")[0], '%Y-%m-%d %H:%M:%S')
        except:
            formatted_time = item["date"]

        properties["messages"].append(f"Author: {item["author"]}, created: {formatted_time}, text: {item["text"]}, attachments: {[img for img in item["attachments"]]}")
        
        try:
            properties["resource_id"] = item["resource_id"]
        except:
            pass # will not be available for replies, only first comment

        properties["text_html"] += f"<b>{item["author"]}</b> at {formatted_time}: <br> &emsp; {item["text"]}<br>"
        for img in item["attachments"]:
            properties["text_html"] += f" <i> &emsp; '{img}'</i> <br>"
            properties["all_attachments"].append(img)

        properties["text_html"] += "<br>"

        #properties["author"] = comment["author"]
        #properties["date"] = comment["date"]
        #properties["text"] = comment["text"]
        #properties["attachments"] = comment["attachments"]



def create_features(self: "SpeckleProvider", context_list: List["TraversalContext"], comments: Dict, data: Dict) -> None:
    """Create features from the list of traversal context."""

    from pygeoapi.provider.speckle_utils.coords_utils import reproject_bulk

    all_coords = []
    all_coord_counts = []
    initialize_features(self, all_coords, all_coord_counts, data, context_list, comments)
    all_features = data["features"] + data["comments"]
    reproject_bulk(self, all_coords, all_coord_counts, [f["geometry"] for f in all_features])
