# pygeoapi with dashboard skin

These directories contain a Docker build script necessary to setup a minimal
`pygeoapi` server that uses a customised dashboard skin.

The skin is pulled in from https://github.com/pvgenuchten/pygeoapi-skin-dashboard

Note that this exmaple is only for local development and testing.

## Building and running

```bash
# build image locally
docker build -t geopython/pygeoapi-skinned:local .
# run container in localhost
docker run -p 5000:80 geopython/pygeoapi-skinned:local
```

Browse to http://localhost:5000
