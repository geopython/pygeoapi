# pygeoapi Docker How To

## Overview

pygeoapi's official Docker image is available on [Docker Hub](https://hub.docker.com/r/geopython/pygeoapi).  `geopython/pygeoapi:latest` is the latest
image based on the master branch; there also exist images for official releases/versions.

## Build workflow

The `latest` version is automatically built whenever code in the `master` branch of this GitHub repository changes (autobuild).

This also cascades to updating the [pygeoapi demo master service](https://demo.pygeoapi.io/master).

So the build chain is as per below:

```
 (git push to master) --> (Docker Hub image autobuild) --> (demo.pygeoapi.io server redeploy)
```

## Setup

The official Docker image ships with a default configuration [default.config.yml](default.config.yml) with the project's test data and OGC API dataset collections.

You can override this default config via a Docker volume mapping or by extending the Docker image and copying in your config.  See an [example from the pygeoapi demo server](https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi) for the latter method.

## Installing on a fresh Ubuntu installation


```bash
# install Docker

sudo apt-get install -y apt-transport-https
sudo apt-get install -y ca-certificates
sudo apt-get install -y curl
sudo apt-get install -y gnupg-agent
sudo apt-get install -y software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add –
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io
sudo systemctl enable docker

# pull official pygeoapi image from Docker Hub

docker pull geopython/pygeoapi

# Create your own configuration in $HOME/my.config.yml
# Example can be found in https://github.com/geopython/pygeoapi-examples/blob/main/docker/simple/my.config.yml
vi $HOME/my.config.yml

# run and create container

sudo docker run --name pygeoapi -p 5000:80 -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi
```

At this point, go to <http://localhost:5000> and the service should be up and running.

## Running - basics

By default, this image will start a `pygeoapi` Docker container using `gunicorn` running on port 80 internally.

To run with the default built-in configuration and data:

```bash
docker run -p 5000:80 -it geopython/pygeoapi run
# or simply
docker run -p 5000:80 -it geopython/pygeoapi

# then browse to http://localhost:5000
```

You can also run all unit tests to verify:

```bash
docker run -it geopython/pygeoapi test
```

## Running - overriding the default config

Normally you would override the [default.config.yml](default.config.yml) with your own configuration.

This can be achieved using Docker volume mapping.  For example, if your config is in `my.config.yml`:

```bash
docker run -p 5000:80 -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi
```

You can also achieve the same using Docker Compose:

```yaml
version: "3"

services:
  pygeoapi:
    image: geopython/pygeoapi:latest
    volumes:
      - ./my.config.yml:/pygeoapi/local.config.yml
```

Or, you can create a `Dockerfile` extending the base image and `COPY` in your config:

```dockerfile
FROM geopython/pygeoapi:latest
COPY ./my.config.yml /pygeoapi/local.config.yml
```

An example using the demo server setup can be found at <https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi_master>.

## Running - running on a sub-path

By default the `pygeoapi` Docker image will run from the root path of the web server (`/`).

If you need to run from a sub-path and have all internal URLs correct, you need to set `SCRIPT_NAME` environment variable.

For example to run with `my.config.yml` on http://localhost:5000/mypygeoapi:

```bash
docker run -p 5000:80 -e SCRIPT_NAME='/mypygeoapi' -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi
# browse to http://localhost:5000/mypygeoapi
```

You can also achieve the same using Docker Compose:

```yaml
version: "3"

services:
  pygeoapi:
    image: geopython/pygeoapi:latest
    volumes:
      - ./my.config.yml:/pygeoapi/local.config.yml
    ports:
      - "5000:80"
    environment:
     - SCRIPT_NAME=/pygeoapi
```

See the [pygeoapi demo service](https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi) for a full example.

## More examples

The [pygeoapi examples](https://github.com/geopython/pygeoapi-examples) repository contains a number of sample deployment configurations.  See
the [docker](https://github.com/geopython/pygeoapi-examples/tree/main/docker) directory for Docker and Docker Compose specific examples.
