#!/bin/sh
set +e
 
echo  "Waiting for the ES to be up to generate openapi yml"
/wait-for elastic_search:9200  -- /run_pygeoapi.sh 

if [ $? -eq 1 ]; then
  "Wait for returned an error, carry on with out ES"
  /run_pygeoapi.sh
fi
exec $@ 