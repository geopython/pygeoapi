# pygeoapi with MongoDB

These folders contain a Docker Compose configuration necessary to setup a minimal
`pygeoapi` server that uses a local MongoDB backend service. Mongo Express is also provided, for convenience.

This config is only for local development and testing.

## MongoDB

- official MongoDB: **5.0.3** on **Ubuntu Focal**
- ports **27017**

## Building and Running

These composition does not require building any images. Run the [Docker compose file](docker-compose.yml) in localhost:

```
docker-compose up
```
