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

Docker folder contains 2 sub-folder

- Simple
- Compose

First folder will create a simple docker image with only GeoJSON, CSV as SQLite providers. While the second folder contains a full docker composition to run pygeoapi with ES.

For simple testing and demonstration is more convenient to use the simple image

Docker images have the following settings:
- Alpine edge OS
- spatialite compilation 4.3.0a
- pygeoapi running on port **5000**  


### Simple (image)

Simple sub folder contains a simple implementation of pygeoapi with out ES (only: GeoJSON, CSV and SQLite provider).
```
cd docker/simple
docker build -t pygeoapi:latest .
docker run -p5000:5000 -v /pygeoapi/tests/data pygeoapi:latest
```


## Docker (composition) 

Docker folder contains a docker-composition necessary to build a minimal pygeoapi using the complete set of providers providers (ES needs to be run as a separated service). Composition is only for development and testing in local environment:

#### ES

- oficial elasticsearch:**5.6.8** on **CentosOS 7**
- ports **9300** and **9200**

Elastic search requires the host system to have its virtual memory parameter (**max_map_count**) [here](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html)

```  
sudo sysctl -w vm.max_map_count=262144
```

If the docker composition fails with the following error:
```
docker_elastic_search_1 exited with code 78
```
it is very likely that you forgot to setup the sysctl

#### Building and Running composition:

To build and run the composition in localhost
```
cd docker/compose
sudo sysctl -w vm.max_map_count=262144
docker-compose build
docker-compose up 
``` 