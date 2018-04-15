# pygeoapi

[![Build Status](https://travis-ci.org/geopython/pygeoapi.png)](https://travis-ci.org/geopython/pygeoapi)

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
curl http://localhost:5000/conformance
# feature collection
curl http://localhost:5000/collections/countries
# feature collection limit 100
curl http://localhost:5000/collections/countries/items?limit=100
# feature
curl http://localhost:5000/collections/countries/items/1
# number of hits
curl http://localhost:5000/collections/countries/items?resulttype=hits

```

## Exploring with Swagger UI

```bash
docker pull swaggerapi/swagger-ui
docker run -p 80:8080 swaggerapi/swagger-ui
# go to http://localhost
# enter http://localhost:5000/api and click 'Explore'
```


## Docker

Docker folder contains a docker-composition necessary to build a minimal pygeoapi using the current providers. Composition is only for development and testing in local environment:

#### ES

- oficial elasticsearch:**5.6.8** on **CentosOS 7**
- ports **9300** and **9200**

Elastic search requires the host system to have its virtual memory parameter (**max_map_count**) [here](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html)

```  
sudo sysctl -w vm.max_map_count=262144
```

#### pygeoapi
- alpine edge OS
- spatialite compilation 4.3.0a
- port **5000**


#### Building and Running composition:
```
cd docker
sudo sysctl -w vm.max_map_count=262144
docker-compose build
docker-compose up 
``` 