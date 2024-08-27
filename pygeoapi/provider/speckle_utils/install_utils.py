
import os
import sys
from typing import Optional

_user_data_env_var = "SPECKLE_USERDATA_PATH"
_application_name = "Speckle"

def user_application_data_path() -> "Path":
    """Get the platform specific user configuration folder path"""
    from pathlib import Path

    path_override = _path()
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
                return ensure_folder_exists(Path.home(), ".config")
    except Exception as ex:
        raise Exception("Failed to initialize user application data path.", ex)

def ensure_folder_exists(base_path: "Path", folder_name: str) -> "Path":
    from pathlib import Path

    path = base_path.joinpath(folder_name)
    path.mkdir(exist_ok=True, parents=True)
    return path

def _path() -> Optional["Path"]:
    from pathlib import Path

    """Read the user data path override setting."""
    path_override = os.environ.get(_user_data_env_var)
    if path_override:
        return Path(path_override)
    return None

def connector_installation_path(host_application: str) -> "Path":
    connector_installation_path = user_speckle_connector_installation_path(
        host_application
    )
    connector_installation_path.mkdir(exist_ok=True, parents=True)

    # set user modules path at beginning of paths for earlier hit
    if sys.path[0] != connector_installation_path:
        sys.path.insert(0, str(connector_installation_path))

    # print(f"Using connector installation path {connector_installation_path}")
    return connector_installation_path

def user_speckle_connector_installation_path(host_application: str) -> "Path":
    """
    Gets a connector specific installation folder.
    In this folder we can put our connector installation and all python packages.
    """
    return ensure_folder_exists(
        ensure_folder_exists(
            user_speckle_folder_path(), "connector_installations"
        ),
        host_application,
    )

def user_speckle_folder_path() -> "Path":
    """Get the folder where the user's Speckle data should be stored."""
    return ensure_folder_exists(
        user_application_data_path(), _application_name
    )
