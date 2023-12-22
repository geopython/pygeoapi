# Running pygeoapi with Docker - Examples

This folder contains the sub-folders:

- simple
- elastic
- esri
- mongo
- MVT-elastic
- MVT-tippecanoe
- sensorthings
- skin
- socrata

The [simple](simple) example will run pygeoapi with Docker with your local config.

The [elastic](elastic) example demonstrates a docker compose configuration to run pygeoapi with local Elasticsearch backend.

The [esri](esri) example demonstrates a docker compose configuration to run pygeoapi with ESRI Map and Feature Services backend.

The [mongo](mongo) example demonstrates a docker compose configuration to run pygeoapi with local MongoDB backend.

The [MVT-elastic](MVT-elastic) example demonstrates a docker compose configuration to run pygeoapi with local Elasticsearch MVT backend.

The [MVT-tippecanoe](MVT-tippecanoe) example demonstrates a docker compose configuration to run pygeoapi with tiles on disk, pre-generated using the Tippecanoe backend.

The [sensorthings](sensorthings) example demonstrates various pygeoapi implementations of SensorThings API endpoints.

The [skin](skin) example contains a Docker build script necessary to setup a minimal
pygeoapi server that uses a customised dashboard skin.

The [socrata](socrata) example contains configuration necessary to setup a
pygeoapi server using a remote Socrata Open Data API (SODA) endpoint.