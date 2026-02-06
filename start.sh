#!/bin/bash

# 1. Define the Environment Variables
export PYTHONPATH=$(pwd)
export PYGEOAPI_CONFIG=$(pwd)/pygeoapi-config.yml
export PYGEOAPI_OPENAPI=$(pwd)/indoorgmlapi_bundled.yaml

# 2. Generate the OpenAPI Document
# This creates the 'local.openapi.yml' file from your config. 
# We run this every time to ensure your API changes (like new collections) appear in Swagger.
echo "Regenerating OpenAPI configuration..."
# pygeoapi openapi generate "$PYGEOAPI_CONFIG" --output-file "$PYGEOAPI_OPENAPI"

# 3. Start the Server
echo "Starting pygeoapi server..."
pygeoapi serve