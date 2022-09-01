# pygeoapi with ESRI Map and Feature Services

This folder contains the docker-compose configuration necessary to setup an example
`pygeoapi` server using a remote ESRI Service endpoint.

This config is only for example purposes.

## Hosting features with ArcGIS

Many ArcGIS layers are hosted as Feature Services. A collection of publically available
layers can be found in the [ArcGIS Living Atlas of the World](https://livingatlas.arcgis.com/en/browse/#d=2&q=Feature%20Service).

The ESRI feature provider creates pygeoapi feature collections from hosted layers. In addition to
hosting data from distributed data providers in one place, pygeoapi creates landing pages for
individual features in the layer.

## Building and Running

To build and run the [Docker compose file](docker-compose.yml) in localhost:

```
docker compose up [--build] [-d]
```

Navigate to `localhost:5000`.
