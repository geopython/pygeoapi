# pygeoapi with Socrata

This folder contains the docker-compose configuration necessary to setup an example
`pygeoapi` server using a remote Socrata Open Data API (SODA) endpoint.

This config is only for local development and testing.

## Building and Running

To build and run the [Docker compose file](docker-compose.yml) in localhost:

```
docker compose up [--build] [-d]
```

Navigate to `localhost:5000`.
