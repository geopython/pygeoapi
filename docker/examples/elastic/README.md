# pygeoapi with Elasticsearch (ES)

These folders contain a Docker Compose configuration necessary to setup a minimal
`pygeoapi` server that uses a local ES backend service.

This config is only for local development and testing.

## Elasticsearch

- official Elasticsearch: **8.4.0** on **Ubuntu 20.04.4 LTS (Focal Fossa)**
- ports **9300** and **9200**

ES requires the host system to have its virtual memory
parameter (**max_map_count**) [here](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html)
set as follows:

```
sudo sysctl -w vm.max_map_count=262144
```

If the docker composition fails with the following error:
```
docker_elastic_search_1 exited with code 78
```

it is very likely that you forgot to setup the `sysctl`.

## Building and Running

To build and run the [Docker compose file](docker-compose.yml) in localhost:

```
sudo sysctl -w vm.max_map_count=262144
docker-compose build
docker-compose up
```
