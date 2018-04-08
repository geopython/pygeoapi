#!/bin/sh


# wait for Elasticsearch to start, then run the setup script to
# create and configure the index.
exec /usr/share/elasticsearch/bin/wait-for-it.sh localhost:9200 -- /add_data.sh &
exec $@ 
