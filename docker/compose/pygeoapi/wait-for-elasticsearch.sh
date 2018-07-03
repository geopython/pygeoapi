#!/bin/sh

set -e

host="$1"
shift
cmd="$@"


until $(curl --output /dev/null --silent --head --fail "$host")  ; do
    echo 'Checking if Elastic Search server is up'
    sleep 5
    counter=$((counter+1))
done

# First wait for ES to start...
response=$(curl $host)

until [ "$response" = "200" ]  ; do
    response=$(curl --write-out %{http_code} --silent --output /dev/null "$host")
    >&2 echo "Elastic Search is up but unavailable - No Reponse - sleeping"
    sleep 10

done


# next wait for ES status to turn to green or yellow
health="$(curl -fsSL "$host/_cat/health?h=status")"
health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')" # trim whitespace (otherwise we'll have "green ")

until [ "$health" = 'yellow'  ] || [ "$health" = 'green'  ]  ; do
    health="$(curl -fsSL "$host/_cat/health?h=status")"
    health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"
    >&2 echo "Elastic Search status is not green or yellow - sleeping"
    sleep 10
done

>&2 echo "Elastic Search is up"


exec $cmd