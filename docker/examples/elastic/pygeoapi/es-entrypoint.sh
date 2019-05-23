#!/bin/sh
set +e
 
echo  "Waiting for ElasticSearch container..."

# First wait for ES to be up and then execute the original pygeoapi entrypoint.
/wait-for-elasticsearch.sh http://elastic_search:9200 /entrypoint.sh || echo "ES failed: $?, exit" && exit 1
