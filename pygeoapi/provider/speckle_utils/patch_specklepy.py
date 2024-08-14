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
    
    file_path = get_transport_path()

    with open(file_path, "r") as file:
        lines = file.readlines()
        new_lines = []
        for i, line in enumerate(lines):

            if 'if self.account is not None:' in line:
                line = line.replace("if self.account is not None:", "if self.account.token is not None:")
            
            if 'lines = r.iter_lines(decode_unicode=True)' in line:
                line = line.replace('lines = r.iter_lines(decode_unicode=True)', 'lines = r.iter_lines(decode_unicode=True, delimiter="},{")')
            
            if 'for line in lines:' in line:
                line1 = line.replace('for line in lines:','all_lines = [line for _,line in enumerate(lines)]')
                new_lines.append(line1)
                line = line.replace('for line in lines:','for i, line in enumerate(all_lines):')
            if 'hash, obj = line.split("\\t")' in line:
                line1 = line.replace('hash, obj = line.split("\\t")','hash = line.split(\'"id": "\')[1].split(\'"\')[0]')
                line2 = line.replace('hash, obj = line.split("\\t")','obj = "{" + line + "}"')
                line3 = line.replace('hash, obj = line.split("\\t")','if i==0:')
                line4 = line.replace('hash, obj = line.split("\\t")','    obj = obj[2:]')
                line5 = line.replace('hash, obj = line.split("\\t")','elif i==len(all_lines)-1:')
                new_lines.extend([line1, line2, line3, line4, line5])

                line = line.replace('hash, obj = line.split("\\t")','    obj = obj[:-2]')
            
            new_lines.append(line)
    file.close()

    with open(file_path, "w") as file:
        file.writelines(new_lines)
    file.close()
    
def copy_gis_feature():
    shutil.copyfile(get_gis_feature_path_src(), get_gis_feature_path_dst())
