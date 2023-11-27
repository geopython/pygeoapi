# Setting up a pygeoapi server with SensorThings (STA) using Docker Compose

This folder contains a Docker Compose configuration necessary to setup an example `pygeoapi` server using a STA endpoint. 

This config is only for local development and testing.

## Introduction

The `pygeoapi` server with SensorThings (STA) provides a platform for publishing SensorThings API data as features. [SensorThings](https://github.com/opengeospatial/sensorthings) is a standardized way to provide access to Internet of Things (IoT) data, making it easier to manage and interact with sensor data.

## SensorThings Build options

There are two example SensorThings API (STA) endpoints available. To switch between examples, you need to change the `pygeoapi.config.yml` file used in the [Docker Compose file](docker-compose.yml).

1. [**brgm.config.yml**](brgm.config.yml): Configures a `pygeoapi` server to serve water quality data from BRGM (Bureau de Recherches Géologiques et Minières), the French Geological Survey.

2. [**usgs.config.yml**](usgs.config.yml): Configures a `pygeoapi` server to serve data from the United States Geological Survey (USGS).


### Additional details
- [**docker-compose.yml**](docker-compose.yml): Defines the Docker Compose configuration for orchestrating the `pygeoapi` server examples. It specifies the Docker image to use, the ports to expose, and the volumes to mount.

- The BRGM water quality endpoint provides access to water quality data from BRGM, the French Geological Survey.

- The USGS data endpoint provides access to data from the United States Geological Survey (USGS).

### Which build option should I choose?

The best build option for you will depend on your specific needs. If you are interested in accessing water quality data from the BRGM, then you should choose the `brgm.config.yml` file. If you are interested in accessing data from the USGS, then you should choose the `usgs.config.yml` file.

If you are not sure which build option to choose, you can start with the `brgm.config.yml` file. This is the simplest build option and it provides access to a _real-world dataset_.

## SensorThings Usage

After editing the [docker-compose.yml](docker-compose.yml) file appropriately, you can start the `pygeoapi` container using the following command:

```bash
docker compose up [-d]
```

This command will create and start the pygeoapi container, republishing SensorThings data. You can then access the pygeoapi server at http://localhost:5000.

## Stopping and Removing Containers

To stop and remove the containers, use the following command:

```bash
docker compose down
```

Please ensure you have the necessary requirements installed before following the setup instructions.