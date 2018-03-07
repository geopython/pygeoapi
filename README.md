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
python flask_app.py

```

Edit `local.config.yml` and `local.swagger.yml`

## Example requests

Try the swagger ui at `http://localhost:5000/ui`

or

```bash
# feature collection metadata
curl http://localhost:5000/
curl http://localhost:5000/api
curl http://localhost:5000/obs
curl http://localhost:5000/obs/371
```
