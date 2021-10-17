#!/bin/bash

mongoimport --db demo -c collectionname --file "/mongo_data/output.geojson" --jsonArray
