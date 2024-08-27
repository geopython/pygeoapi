import sys 
from pathlib import Path
import shutil
import pygeoapi


def get_specklepy_path():
    import specklepy

    return Path(specklepy.__file__).parent

def get_pygeoapi_path():

    return Path(pygeoapi.__file__).parent


def get_credentials_path():
    specklepy_path = get_specklepy_path()
    credentials_path = Path(specklepy_path, "core", "api", "credentials.py")

    return str(credentials_path)

def get_transport_path():
    specklepy_path = get_specklepy_path()
    credentials_path = Path(specklepy_path, "transports", "server", "server.py")

    return str(credentials_path)

def get_transport_path_src():
    credentials_path = Path(get_pygeoapi_path(), "provider", "speckle_utils", "patch", "server.py")

    return str(credentials_path)

def get_serializer_path():
    specklepy_path = get_specklepy_path()
    credentials_path = Path(specklepy_path, "serialization", "base_object_serializer.py")

    return str(credentials_path)

def get_serializer_path_src():
    credentials_path = Path(get_pygeoapi_path(), "provider", "speckle_utils", "patch", "base_object_serializer.py")

    return str(credentials_path)

def get_gis_feature_path_src():
    credentials_path = Path(get_pygeoapi_path(), "provider", "speckle_utils", "patch", "GisFeature.py")

    return str(credentials_path)

def get_gis_feature_path_dst():
    specklepy_path = get_specklepy_path()
    credentials_path = Path(specklepy_path, "objects", "GIS", "GisFeature.py")

    return str(credentials_path)

def patch_credentials():
    """Patches the installer with the correct connector version and specklepy version"""
    
    file_path = get_credentials_path()

    with open(file_path, "r") as file:
        lines = file.readlines()
        new_lines = []
        for i, line in enumerate(lines):
            if "Account.model_validate_json" in line:
                line = line.replace("Account.model_validate_json", "Account.parse_raw")
            new_lines.append(line)
    file.close()

    with open(file_path, "w") as file:
        file.writelines(new_lines)
    file.close()
    
def patch_transport():
    """Patches the installer with the correct connector version and specklepy version"""
    
    server_data = get_transport_path_src()
    file_path = get_transport_path()

    with open(server_data, "r") as file:
        lines = file.readlines()
    file.close()

    with open(file_path, "w") as file:
        file.writelines(lines)
    file.close()
    
def patch_serializer():
    """Patches the installer with the correct connector version and specklepy version"""
    
    server_data = get_serializer_path_src()
    file_path = get_serializer_path()

    with open(server_data, "r") as file:
        lines = file.readlines()
    file.close()

    with open(file_path, "w") as file:
        file.writelines(lines)
    file.close()
    
def complete_patch():
    """Patches the installer with the correct connector version and specklepy version"""
    
    # check file 1
    file_path = get_transport_path()
    with open(file_path, "r") as file:
        lines = file.readlines()
    file.close()

    if len(lines) < 184:
        return False
    
    # check file 1
    file_path = get_serializer_path()
    with open(file_path, "r") as file:
        lines = file.readlines()
    file.close()

    if len(lines) < 443:
        return False
    
    return True
    
def copy_gis_feature():
    shutil.copyfile(get_gis_feature_path_src(), get_gis_feature_path_dst())

def patch_specklepy():

    #if complete_patch():
    #    return
    
    patch_credentials()
    copy_gis_feature()
    patch_transport()
    patch_serializer()

if __name__ == "__main__":
    patch_specklepy()
    