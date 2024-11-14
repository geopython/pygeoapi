#!/bin/bash

echo "shared_preload_libraries = 'postgis-3.so'" >> $PGDATA/postgresql.conf

set -e

# Create the 'mobilitydb' extension in the mobilitydb database
echo "Loading MobilityDB extension into mobilitydb"
psql --user="$POSTGRES_USER" --dbname="mobilitydb" <<- 'EOSQL'
	CREATE EXTENSION IF NOT EXISTS PostGIS;
  CREATE EXTENSION IF NOT EXISTS mobilitydb CASCADE;
  CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    
    -- Table collection
  CREATE TABLE public.collection (
    collection_id uuid NOT NULL DEFAULT uuid_generate_v4(),
    collection_property jsonb NULL,
    PRIMARY KEY (collection_id)
  );

    -- Table MovingFeature
  CREATE TABLE public.mfeature (
    collection_id uuid NOT NULL,
    mfeature_id uuid NOT NULL DEFAULT uuid_generate_v4(),
    mf_geometry geometry NULL,
    mf_property jsonb NULL,
    lifespan tstzspan NULL,
      PRIMARY KEY (collection_id, mfeature_id),
      FOREIGN KEY (collection_id) REFERENCES collection(collection_id)
  );

    -- Table TemporalGeometry
  CREATE TABLE public.tgeometry (
    collection_id uuid NOT NULL,
    mfeature_id uuid NOT NULL,
    tgeometry_id uuid NOT NULL DEFAULT uuid_generate_v4(),
    tgeometry_property tgeompoint NULL,
    tgeog_property tgeompoint NULL,
    PRIMARY KEY (collection_id, mfeature_id, tgeometry_id),
    FOREIGN KEY (collection_id, mfeature_id) REFERENCES mfeature(collection_id, mfeature_id)
  );

    -- Table TemporalProperty
  CREATE TABLE public.tproperties (
    collection_id uuid NOT NULL,
    mfeature_id uuid NOT NULL,
    tproperties_name text NOT NULL,
    datetime_group int4 NOT NULL,
    tproperty jsonb NULL,
    pvalue_float tfloat NULL,
    pvalue_text ttext NULL,
    PRIMARY KEY (collection_id, mfeature_id, tproperties_name, datetime_group),
    FOREIGN KEY (collection_id, mfeature_id) REFERENCES mfeature(collection_id, mfeature_id)
  );
EOSQL
