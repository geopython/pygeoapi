# pygeoapi Docker How To

Docker Image `geopython/pygeoapi:latest` and versions are [available from DockerHub](https://hub.docker.com/r/geopython/pygeoapi).

Each Docker Image contains a default configuration [default.config.yml](default.config.yml) with the project's test data and OGC API dataset collections.

You can override this default config via Docker Volume mapping or by extending the Docker Image and copying in your config. See an [example for the geoapi demo server](https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi) for the latter method.

https://github.com/geopython/demo.pygeoapi.io/tree/master/services Depending on your config you may need specific backends to be available.

### Background

The version tagged `latest` is automatically built whenever code in the `master` branch of this GitHub repo changes (autobuild). This also cascades to updating the [pygeoapi demo service](https://demo.pygeoapi.io/master).

So the chain is:

```
 (git push to master) --> (DockerHub Image autobuild) --> (demo server redeploy)

```

There are a number of examples at [several examples](https://github.com/geopython/pygeoapi/blob/master/docker/examples).

### Installation

Install Docker (Ubuntu)

```bash
sudo apt-get install apt-transport-https
sudo apt-get install ca-certificates
sudo apt-get install curl
sudo apt-get install gnupg-agent
sudo apt-get install software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add –
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io
sudo systemctl enable docker
```
Pull dockerhub repo

```bash
docker pull geopython/pygeoapi
```
Create your own my.config.yml (https://github.com/geopython/pygeoapi/blob/master/docker/examples/simple/my.config.yml) in home directory

Run/Create Container

``` bash
$ sudo docker run --name geoapi -p 5000:80 -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi
```

Go to http://localhost:5000/ and should be up and running.

## Running - Basics

By default this Image will start a `pygeoapi` Docker Container
using `gunicorn` on internal port 80.

To run with default built-in config and data:

```
	docker run -p 5000:80 -it geopython/pygeoapi run
	# or simply
	docker run -p 5000:80 -it geopython/pygeoapi

    # then browse to http://localhost:5000/
```

You can also run all unit tests to verify:

```
	docker run -it geopython/pygeoapi test
```

## Running - Overriding the default config

Normally you would override the [default.config.yml](default.config.yml) with your own `pygeoapi` config.
This can be effected best via Docker Volume Mapping.

For example if your config is in `my.config.yml`:

```
	docker run -p 5000:80 -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi
```

But better/cleaner is to use `docker-compose`. Something like:

```
version: "3"

services:

  pygeoapi:
    image: geopython/pygeoapi:latest

    volumes:
      - ./my.config.yml:/pygeoapi/local.config.yml

```

Or you can create a `Dockerfile` extending the base Image and `COPY` in your config:

```
FROM geopython/pygeoapi:latest

COPY ./my.config.yml /pygeoapi/local.config.yml

```

See how the demo server is setup this way at
https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi_master

## Running - Running on a sub-path

By default the `pygeoapi` Docker Image will run from the `root` path `/`.
If you need to run from a sub-path and have all internal URLs correct
you need to set `SCRIPT_NAME` environment variable.

For example to run with `my.config.yml` on http://localhost:5000/mypygeoapi:

```
	docker run -p 5000:80 -e SCRIPT_NAME='/mypygeoapi' -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi
	# browse to http://localhost:5000/mypygeoapi
```

Or within a `docker-compose.yml` full example:

```
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

See [pygeoapi demo service](https://github.com/geopython/demo.pygeoapi.io/tree/master/services/pygeoapi)
for an full example.



