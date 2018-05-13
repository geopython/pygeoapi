#!/bin/sh

set +e
echo "Trying to generate openapi.yml"
cd /pygeoapi

pygeoapi generate_openapi_document -c local.config.yml > openapi.yml




if [ $? -ne 0 ] ; then
       echo "openapi.yml couldnt be generate ERROR, but carry on"
 else
 	   echo "openapi.yml generated continue to pygeoapi"
 fi

pygeoapi serve


