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
cp openapi/wfs/0.0.1/swagger.yaml local.swagger.yaml
cp config.yaml local.config.yaml
python flask_app.py
```

Edit `local.config.yaml` and `local.swagger.yml`

## Example requests

```bash
# feature collection metadata
curl http://localhost:5000/
```
