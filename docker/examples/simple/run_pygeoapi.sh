#!/bin/sh

echo "Running latest Docker version of pygeoapi with local config"
echo "Go with your browser to http://localhost:5000 to view"
docker run -p 5000:80 -v $(pwd)/my.config.yml:/pygeoapi/local.config.yml -it geopython/pygeoapi:latest

