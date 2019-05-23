# Simple Example

This is the simplest example to run `pygeoapi` with a [local config](my.config.yml)
using Docker.

## Using Docker directly

Execute [./run_pygeoapi.sh](run_pygeoapi.sh). This will pull the `pygeoapi` Image from
DockerHub and start the `pygeoapi` server. With your browser got to http://localhost:5000.

## Using Docker Compose

Run the [docker-compose.yml](docker-compose.yml) as follows:

```
docker-compose up [-d]

```
