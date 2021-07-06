# Pygeoapi with SensorThings (STA)

This folder contains a Docker Compose configuration necessary to setup an example
`pygeoapi` server using a STA endpoint. 

This config is only for local development and testing.

## SensorThings Build options

There are three example STA endpoints. To switch between examples, the `pygeoapi.config.yml` file used in the docker
compose needs to be changed.

- The first, [brgm.sta.pygeoapi.config.yml](brgm.sta.pygeoapi.config.yml) creates a `pygeoapi` server serving the BRGM water quality endpoint. 

- The second, [iow.sta.pygeoapi.config.yml](iow.sta.pygeoapi.config.yml) creates a `pygeoapi` server hosting example IoW endpoint with URIs. 

- The final config, [sta.pygeoapi.config.yml](sta.pygeoapi.config.yml) creates a `pygeoapi` server inside of a muti-container Docker app,
and linked to an empty [FROST server](https://fraunhoferiosb.github.io/FROST-Server/). To use this configuration, 
uncomment Lines 40 - 70 of the docker-compose.yml file in addition to changing the pygeoapi config. The 
database can be populated following a workflow similar to that of the populator script for build testing, `load_sta_data.py`.
`Note: The pygeoapi server will fail to build until the STA server has been populated, thus the addition of always restart`

## SensorThings Usage

After editing the [docker-compose.yml](docker-compose.yml) file appropriately:

```
docker compose up [-d]
```

Navigate to `localhost:5000`.