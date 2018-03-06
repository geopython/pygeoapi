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
cp pygeoapi-config.yml local.yml
vi local.yml
# update server.url
# add ES dataset(s) to datasets section
export PYGEOAPI_CONFIG=`pwd`/local.yml
python3 pygeoapi/app.py
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
