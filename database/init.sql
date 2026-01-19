-- Enable PostGIS extension immediately
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TYPE "spcaetype" AS ENUM (
  'primal',
  'dual'
);

CREATE TYPE "celltype" AS ENUM (
  'space',
  'boundary'
);

CREATE TYPE "node_edge_type" AS ENUM (
  'node',
  'edge'
);

CREATE TYPE "topo_type" AS ENUM (
  'CONTAINS',
  'OVERLAPS',
  'EQUALS',
  'WITHIN',
  'CROSSES',
  'OTHERS'
);

CREATE TABLE "collection" (
  "id" bigint PRIMARY KEY,
  "id_str" varchar UNIQUE,
  "collection_property" jsonb
);

CREATE TABLE "indoorfeature" (
  "id" bigint PRIMARY KEY,
  "id_str" varchar UNIQUE,
  "collection_id" bigint NOT NULL,
  "geojson_geometry" geometry,
  "geojson_properties" jsonb
);

CREATE TABLE "thematiclayer" (
  "id" bigint PRIMARY KEY,
  "id_str" varchar UNIQUE,
  "space_id_str" varchar UNIQUE,
  "collection_id" bigint NOT NULL,
  "indoorfeature_id" bigint NOT NULL,
  "semantic_extension" bool NOT NULL,
  "space_type" spcaetype,
  "creation_datetime" timestamp,
  "termination_datetime" timestamp,
  "is_logical" bool,
  "is_directed" bool
);

CREATE TABLE "cell_space_n_boundary" (
  "id" bigint PRIMARY KEY,
  "id_str" varchar UNIQUE,
  "type" celltype NOT NULL,
  "collection_id" bigint NOT NULL,
  "indoorfeature_id" bigint NOT NULL,
  "thematiclayer_id" bigint NOT NULL,
  "2D_geometry" geometry,
  "3D_geometry" geometry,
  "cell_name" varchar,
  "duality_id" bigint,
  "level" varchar,
  "poi" bool,
  "is_virtual" bool,
  "external_reference" jsonb,
  "bounded_by_cell_id" bigint
);

CREATE TABLE "node_n_edge" (
  "id" bigint PRIMARY KEY,
  "id_str" varchar UNIQUE,
  "type" node_edge_type NOT NULL,
  "collection_id" bigint NOT NULL,
  "indoorfeature_id" bigint NOT NULL,
  "thematiclayer_id" bigint NOT NULL,
  "geometry_val" geometry,
  "duality_id" bigint,
  "weight" float
);

CREATE TABLE "connects" (
  "node_source_id" bigint NOT NULL,
  "node_target_id" bigint NOT NULL,
  "edge_id" bigint NOT NULL
);

CREATE TABLE "interlayerconnection" (
  "id" bigint PRIMARY KEY,
  "id_str" varchar,
  "collection_id" bigint NOT NULL,
  "indoorfeature_id" bigint NOT NULL,
  "connected_layer_a" bigint NOT NULL,
  "connected_layer_b" bigint NOT NULL,
  "connected_cell_a" bigint,
  "connected_cell_b" bigint,
  "connected_node_a" bigint,
  "connected_node_b" bigint,
  "comment" varchar
);

ALTER TABLE "indoorfeature" ADD FOREIGN KEY ("collection_id") REFERENCES "collection" ("id");

ALTER TABLE "thematiclayer" ADD FOREIGN KEY ("collection_id") REFERENCES "collection" ("id");

ALTER TABLE "thematiclayer" ADD FOREIGN KEY ("indoorfeature_id") REFERENCES "indoorfeature" ("id");

ALTER TABLE "cell_space_n_boundary" ADD FOREIGN KEY ("collection_id") REFERENCES "collection" ("id");

ALTER TABLE "cell_space_n_boundary" ADD FOREIGN KEY ("indoorfeature_id") REFERENCES "indoorfeature" ("id");

ALTER TABLE "cell_space_n_boundary" ADD FOREIGN KEY ("thematiclayer_id") REFERENCES "thematiclayer" ("id");

ALTER TABLE "node_n_edge" ADD FOREIGN KEY ("collection_id") REFERENCES "collection" ("id");

ALTER TABLE "node_n_edge" ADD FOREIGN KEY ("indoorfeature_id") REFERENCES "indoorfeature" ("id");

ALTER TABLE "node_n_edge" ADD FOREIGN KEY ("thematiclayer_id") REFERENCES "thematiclayer" ("id");

ALTER TABLE "connects" ADD FOREIGN KEY ("node_source_id") REFERENCES "node_n_edge" ("id");

ALTER TABLE "connects" ADD FOREIGN KEY ("node_target_id") REFERENCES "node_n_edge" ("id");

ALTER TABLE "connects" ADD FOREIGN KEY ("edge_id") REFERENCES "node_n_edge" ("id");

ALTER TABLE "interlayerconnection" ADD FOREIGN KEY ("collection_id") REFERENCES "collection" ("id");

ALTER TABLE "interlayerconnection" ADD FOREIGN KEY ("indoorfeature_id") REFERENCES "indoorfeature" ("id");

ALTER TABLE "interlayerconnection" ADD FOREIGN KEY ("connected_layer_a") REFERENCES "thematiclayer" ("id");

ALTER TABLE "interlayerconnection" ADD FOREIGN KEY ("connected_layer_b") REFERENCES "thematiclayer" ("id");