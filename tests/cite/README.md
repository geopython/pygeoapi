# CITE testing for OGC API capabilities

- OGC API - Features
- OGC API - Processes

## Test data

### OGC API - Features
Test data used is a subset of the [Canadian National Water Data Archive](https://www.canada.ca/en/environment-climate-change/services/water-overview/quantity/monitoring/survey/data-products-services/national-archive-hydat.html) as extracted from the [MSC GeoMet OGC API](https://eccc-msc.github.io/open-data/msc-geomet/web-services_en/#ogc-api-features) service.

### OGC API - Processes
The `hello-world` test process that is provided with pygeoapi by default is used.

Process job management is configured in `server.manager` in support of asynchronous testing.

## Running

```bash
# install pygeoapi as per https://pygeoapi.io/#install-in-5-minutes
# the service needs to run with HTTP 1.1 support, so let's install gunicorn
# remove job manager
rm -f /tmp/pygeoapi-process-manager.db*
pip3 install gunicorn
cd tests/cite
. cite.env
python3 ../load_es_data.py ./canada-hydat-daily-mean-02hc003.geojson IDENTIFIER
pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI
gunicorn pygeoapi.flask_app:APP -b 0.0.0.0:5001 --access-logfile '-'
```
