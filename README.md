# pygeoapi
pygeoapi provides an API to geospatial data

## Installation

```bash
virtualenv pygeoapi
cd pygeoapi
. bin/activate
git clone https://github.com/geopython/pygeoapi.git
cd pygeoapi
git checkout flask-app
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp pygeoapi-config.yml local.yml
vi local.yml
# update server.url
# add ES dataset(s) to datasets section
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
curl http://localhost:5000/my-dataset
# feature
curl http://localhost:5000/my-dataset/featureid
```
