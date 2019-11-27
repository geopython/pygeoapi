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
# install provider requirements accordingly from requirements-provider.txt
# install starlette requirements accordingly from requirements-starlette.txt
pip install -e .
cp pygeoapi-config.yml local.config.yml
vi local.config.yml
# TODO: what is most important to edit?
export PYGEOAPI_CONFIG=$(pwd)/local.config.yml
# generate OpenAPI Document
pygeoapi generate-openapi-document -c local.config.yml > openapi.yml
export PYGEOAPI_OPENAPI=$(pwd)/openapi.yml
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
# enter http://localhost:5000/openapi and click 'Explore'
```

## Demo Server

There is a demo server on https://demo.pygeoapi.io running the latest (Docker) version
from the `master` branch of this repo. `pygeoapi` runs there at https://demo.pygeoapi.io/master.

The demo server setup and config is maintained within a seperate GH repo:
https://github.com/geopython/demo.pygeoapi.io.

## Docker

Best/easiest way to run `pygeoapi` is to use Docker.
On DockerHub [pygeoapi Docker Images](https://hub.docker.com/r/geopython/pygeoapi)
are available.

The version tagged `latest` is automatically built whenever code
in the `master` branch of this GitHub repo changes (autobuild).
This also cascades to updating the [pygeoapi demo service](https://demo.pygeoapi.io/master).
So the chain is:

```
 (git push to master) --> (DockerHub Image autobuild) --> (demo server redeploy)

```

Please read the [docker/README](https://github.com/geopython/pygeoapi/blob/master/docker/README.md) for
details of the Docker implementation. To get started quickly
[several examples](https://github.com/geopython/pygeoapi/blob/master/docker/examples) will get you up and running.

## Development

### Unit Testing

Unit tests are run using `pytest` from the top project folder:

```sh
pytest tests
```

NB beware that some tests require Provider dependencies (libraries) to be available
and that the ElasticSearch and Postgres tests require their respective
backend servers running.

Running a subset of the tests is possible, e.g.:

```sh
pytest tests/test_api.py`
```

Environment variables are set in the file [pytest.ini](pytest.ini).

### Linting and formatting

[`black`](https://github.com/psf/black) is used for auto-formatting code; [`flake8`](https://pypi.org/project/flake8/) is used to check compliance against [PEP 8](https://www.python.org/dev/peps/pep-0008/). These tools are combined into an automatic workflow with [`pre-commit`](https://pre-commit.com/). When you attempt to commit, pre-commit will first auto-format any Python files that you changed; then it will check PEP 8 compliance. You will have the opportunity to review the automatic changes (since you will need to `git add` them again).

You will need the development dependencies (`requirements-dev.txt`) installed. Then run
```sh
pre-commit install
```
to install the pre-commit hooks into `.git`. Now whenever you commit, these checks will automatically operate.
