
from typing import Dict, List


def assign_props(obj: "Base", props: Dict):
    """Assign properties to the feature from Base object."""

    from specklepy.objects.geometry import Base
    from specklepy.objects.other import RevitParameter

    all_prop_names = obj.get_member_names()
    dynamic_prop_names = obj.get_dynamic_member_names()
    typed_prop_names = obj.get_typed_member_names()

    # check if GIS object
    if "attributes" in all_prop_names and isinstance(obj["attributes"], Base):
        all_prop_names = obj["attributes"].get_dynamic_member_names()
        for prop_name in all_prop_names:

            value = getattr(obj["attributes"], prop_name)

            if (prop_name
                in [
                    "geometry",
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
    
    # if Rhino: 
    elif "userStrings" in dynamic_prop_names and isinstance(obj["userStrings"], Base):
        all_prop_names = obj["userStrings"].get_dynamic_member_names()

        for prop_name in all_prop_names:

            if prop_name in ["id"]:
                continue

            value = getattr(obj["userStrings"], prop_name)
            if not isinstance(value, str):
                props[prop_name] = str(value)
            else:
                props[prop_name] = value
        return 
            
    for prop_name in obj.get_dynamic_member_names():
        if (
            prop_name
            in [
                "displayValue",
                "displayStyle",
                "renderMaterial",
                "revitLinkedModelPath",
                "id",
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
    
    # if Revit: 
    if "parameters" in all_prop_names and isinstance(obj.parameters, Base):
        for prop_name in obj.parameters.get_dynamic_member_names():
            if prop_name in ["id","revitLinkedModelPath"]:
                continue

            param = getattr(obj.parameters, prop_name)
            if isinstance(param, RevitParameter):
                
                if not isinstance(param.value, str):
                    props[prop_name] = str(param.value)
                else:
                    props[prop_name] = param.value
        # add after dynamic parameters


def assign_missing_props(features: Dict, all_props: List[str]) -> None:
    """Assign NA values to missing properties."""

    # assign all props to all features
    for feat in features:
        for prop in all_props:
            if prop not in list(feat["properties"].keys()):
                feat["properties"][prop] = "N/A"
