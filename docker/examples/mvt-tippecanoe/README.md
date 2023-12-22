# pygeoapi with Tippecanoe MVT

These folders contain a Docker Compose configuration necessary to setup a minimal
`pygeoapi` server that uses pre-rendered [Tippecanoe](https://github.com/mapbox/tippecanoe) Mapbox Vector Tiles to publish vector data as OGC API - Tiles.

More information about this provider, including the features it supports, can be found on the [pygeoapi documentation](https://docs.pygeoapi.io/en/latest/data-publishing/ogcapi-tiles.html#providers#mvt-tippecanoe).

This config is only for local development and testing.

## Tippecanoe

This example uses the test tiles, available on ```tests/data/tiles/ne_110m_lakes/```. You can generate your own tiles on disk with:

``` bash
docker run -it --rm -v $(pwd)/data:/data emotionalcities/tippecanoe \
tippecanoe --output-to-directory=/data/tiles/ --force --maximum-zoom=16 --drop-densest-as-needed --extend-zooms-if-still-dropping --no-tile-compression /data/ne_110m_populated_places_simple.geojson
```

## Building and Running

To build and run the [Docker compose file](docker-compose.yml) in localhost:

```
docker-compose up
```