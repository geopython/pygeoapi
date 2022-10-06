# pygeoapi with dashboard skin

These folders contain a Docker build script necessary to setup a minimal
`pygeoapi` server that uses a customised dashboard skin. The skin is pulled in from https://github.com/pvgenuchten/pygeoapi-skin-dashboard.

This config is only for local development and testing.

## Building and Running

This builds the required image locally. Then run the container in localhost:

```
docker build -t geopython/pygeoapi-skinned .
docker run -p 5000:80 geopython/pygeoapi-skinned
```

Browse to http://localhost:5000
