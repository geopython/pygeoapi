#!/bin/bash

export PYGEOAPI_CONFIG=pygeoapi-config.yml
export PYGEOAPI_OPENAPI=my-openapi.yml

echo "Generating OpenAPI document..."
#pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI

echo "Starting pygeoapi server..."
pygeoapi serve
