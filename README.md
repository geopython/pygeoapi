# pygeoapi
pygeoapi provides an API to geospatial data

## Installation

```bash
virtualenv -p python3 pygeoapi
cd pygeoapi
. bin/activate
git clone https://github.com/geopython/pygeoapi.git
cd pygeoapi
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
cp pygeoapi-config.yml local.yml
vi local.yml
# update server.url
# add dataset(s) to datasets section
export PYGEOAPI_CONFIG=`pwd`/local.yml
python pygeoapi/app.py
```

## Example requests

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
