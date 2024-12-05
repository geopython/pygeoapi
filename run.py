import os
from pathlib import Path

# we need a config file for PYGEOAPI_CONFIG to work
path_config = r"C:\Users\sjordan\OneDrive - LimnoTech\Documents\GitHub\pygeoapi-limno\config-gdp.yml"
os.environ["PYGEOAPI_CONFIG"] = path_config


# We also need an OpenAI file, but there is tooling to generate that
from pygeoapi.openapi import generate_openapi_document

path_openapi = r"C:\Users\sjordan\OneDrive - LimnoTech\Documents\GitHub\pygeoapi-limno\openapi.yml"
content = generate_openapi_document(Path(path_config), "yaml")

with open(path_openapi, "w") as output:
    output.write(content)

# now set the environment variable
os.environ["PYGEOAPI_OPENAPI"] = path_openapi

from pygeoapi.starlette_app import serve

if __name__ == "__main__":
    serve()
