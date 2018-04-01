# pygeoapi

pygeoapi provides an API to geospatial data

## Installation

```bash
virtualenv -p python pygeoapi
cd pygeoapi
. bin/activate
git clone https://github.com/geopython/pygeoapi.git
cd pygeoapi
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
cp pygeoapi-config.yml local.config.yml
vi local.config.yml
# TODO: what is most important to edit?
export PYGEOAPI_CONFIG=/path/to/local.config.yml
# generate OpenAPI Document
pygeoapi generate_openapi_document -c local.config.yml > openapi.yml
export PYGEOAPI_OPENAPI=/path/to/openapi.yml
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

## Testing against Swagger UI

```bash
docker pull swaggerapi/swagger-ui
docker run -p 80:8080 swaggerapi/swagger-ui
# go to http://localhost
# enter http://localhost:5000/api and click 'Explore'
```
