# pygeoapi

pygeoapi provides an API to geospatial data

## Installation

```bash
virtualenv -p python3 pygeoapi
cd pygeoapi
. bin/activate
git clone https://github.com/geopython/pygeoapi.git
cd pygeoapi
pip3 install -r requirements.txt
pip3 install -r requirements-dev.txt
pip3 install -e .
cp openapi/wfs/0.0.1/pygeoapi-openapi.yml local.swagger.yml
cp pygeoapi-config.yml local.config.yml
vi local.config.yml
# TODO: what is most important to edit?
vi local.swagger.yml
# TODO: what is most important to edit?
export PYGEOAPI_CONFIG=/path/to/local.config.yml
export PYGEOAPI_SWAGGER=/path/to/local.swagger.yml
pygeoapi serve
```

## Example requests

Try the swagger ui at `http://localhost:5000/ui`

or

```bash
# feature collection metadata
curl http://localhost:5000/
# conformance
curl http://localhost:5000/api/conformance
# feature collection
curl http://localhost:5000/obs
# feature
curl http://localhost:5000/obs/371
```
