# CITE testing for OGC API - Features

## Test data

Test data used is a subset of the [Canadian National Water Data Archive](https://www.canada.ca/en/environment-climate-change/services/water-overview/quantity/monitoring/survey/data-products-services/national-archive-hydat.html)
as extracted from the [MSC Geomet OGC API](https://eccc-msc.github.io/open-data/msc-geomet/web-services_en/#ogc-api-features).

## Running

```bash
# install pygeoapi as per https://pygeoapi.io/#install-in-5-minutes
cd tests/cite/ogcapi-features
. cite.env
python load_es_data.py ./canada-hydat-daily-mean-02hc003.json IDENTIFIER
pygeoapi generate-openapi-document -c $PYGEOAPI_CONFIG > $PYGEOAPI_OPENAPI
gunicorn pygeoapi.flask_app:APP -b 0.0.0.0:5001 --access-logfile '-'
```
