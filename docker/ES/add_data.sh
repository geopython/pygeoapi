#!/bin/sh

echo "Starting script to add geojson"
# move to the directory of this setup script
cd "$(dirname "$0")"

# for some reason even when port 9200 is open Elasticsearch is unable to be accessed as authentication fails
# a few seconds later it works
# incresing to 50s for wait in a slow system /_cluster/health?wait_for_status=yellow&timeout=50s
until $(curl -sSf -XGET --insecure 'http://localhost:9200/_cluster/health?wait_for_status=yellow' > /dev/null); do
    printf 'No status yellow from ES, trying again in 10 seconds \n'
    sleep 10
done
echo "SEEMS TO BE WORKING - LETS INJECT DATA"
# create a new index with the settings in es_index_config.json
#curl -v --insecure --user elastic:changeme -XPUT '0.0.0.0:9200/test?pretty' -H 'Content-Type: application/json' -d @es_index_config.json
