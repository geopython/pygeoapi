import sys 
from pathlib import Path
import shutil

def get_specklepy_path():
    root_path = Path(sys.executable).parent.parent
    credentials_path = Path(root_path, "Lib", "site-packages", "specklepy")

    return credentials_path

def get_credentials_path():
    specklepy_path = get_specklepy_path()
    credentials_path = Path(specklepy_path, "core", "api", "credentials.py")

    return str(credentials_path)

def get_transport_path():
    specklepy_path = get_specklepy_path()
    credentials_path = Path(specklepy_path, "transports", "server", "server.py")

    return str(credentials_path)

def get_transport_path_src():
    specklepy_path = Path(sys.executable).parent.parent
    credentials_path = Path(specklepy_path, "pygeoapi", "pygeoapi", "provider", "speckle_utils", "server.py")

    return str(credentials_path)

def get_gis_feature_path_src():
    specklepy_path = Path(sys.executable).parent.parent
    credentials_path = Path(specklepy_path, "pygeoapi", "pygeoapi", "provider", "speckle_utils", "GisFeature.py")

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
    
def complete_transport():
    """Patches the installer with the correct connector version and specklepy version"""
    
    file_path = get_transport_path()

    with open(file_path, "r") as file:
        lines = file.readlines()
    file.close()

    print(len(lines))
    if len(lines) < 184:
        return False
    return True
    
def copy_gis_feature():
    shutil.copyfile(get_gis_feature_path_src(), get_gis_feature_path_dst())

def patch_specklepy():

    if complete_transport():
        return
    
    patch_credentials()
    copy_gis_feature()
    patch_transport()
    