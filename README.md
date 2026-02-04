# IndoorGML API

IndoorGML api is a RESTful api implementation of the **OGC IndoorGML 2.0** standard, designed to align with **OGC API - Features** standards. This api extends the pygeoapi framework to provide specialized service layers for indoor environments.


### About Naming

This API is referred to as the **IndoorGML API** because it implements
the IndoorGML conceptual model, including spatial subdivision, topology,
layering, and duality relationships.

All resources are exchanged using **IndoorJSON**, which serves as the
concrete JSON encoding of IndoorGML concepts.

---

## 🚀 Project Overview

This project is a extension of 
[pygeoapi](https://pygeoapi.io), designed to provide a RESTful API for IndoorGML 2.0 standard.
### Key Accomplishments
* **OGC Standards Alignment:** Successfully mapped IndoorGML 2.0 Indoorfeature to the OGC API - Features core.
* **Dual-Space Logic:** Full implementation of Primal Space (Rooms/Boundaries) and Dual Space (Nodes/Edges) connectivity.
* **Advanced Navigation:** Custom service endpoints for Shortest Path (Dijkstra) and Topological N-Hop analysis.
* **Engineering Precision:** Native support for **SRID 0** (Cartesian Plane) for building-scale accuracy.

---

## 🛠 Technical Pedigree

### Built on [pygeoapi](https://pygeoapi.io)
This engine is built upon a specialized fork of **pygeoapi**, a Python server implementation of the OGC API suite of standards. 
* **Standardized Access:** Provides RESTful endpoints using OpenAPI, GeoJSON, and HTML.
* **Extended Core:** We have customized the `api/indoorgml.py` core and developed custom providers to handle the unique hierarchy of `IndoorFeatures`.
* **PostgreSQL/PostGIS:** Optimized schema for spatial bounding and geometric queries.
* **pgRouting:** Dynamic graph traversal without the overhead of static topology creation.
* **Dockerized:** Fully containerized environment for immediate deployment.

---

## 🗺 System Architecture

### Architectural Overview

The IndoorGML API is designed according to a **separation-of-concerns architecture** that distinguishes between:

- **Persistent storage optimized for spatial querying and data integrity**, and
- **A encoding layer that produces schema-conformant IndoorJSON documents**

The database schema and the API representation are intentionally decoupled.  
The database is treated as an **implementation detail**, while IndoorJSON serves as the **canonical exchange format** exposed to clients.

### Resource diagram

![System Architecture Diagram](./data/indoorfeatures.drawio.svg)

---

### DB–IndoorJSON Mapping Principles

#### Identifier Management

All core entities are assigned:

- a **surrogate numeric identifier** for internal relational operations, and  
- a **stable string identifier** corresponding to the IndoorJSON `"id"` field.

During encoding, string identifiers are emitted verbatim as IndoorJSON identifiers.  
During ingestion, IndoorJSON identifiers are resolved to their corresponding internal keys.

This strategy ensures **identifier stability, referential integrity, and lossless round-trip conversion** between database and IndoorJSON representations.

#### Geometry Representation

IndoorJSON differentiates between two-dimensional and three-dimensional geometries.  
The API adopts the following mapping strategy:

- **2D geometries**
  - Stored in PostGIS geometry columns
  - Used for spatial predicates, bounding-box filtering, geometric queries, and routing
- **3D geometries**
  - Stored as JSON objects conforming to the IndoorJSON geometry model
  - Returned without structural transformation

This approach preserves **computational efficiency for spatial operations** while maintaining **semantic fidelity** to the IndoorJSON specification for volumetric and surface geometries.

#### Layer-Oriented Data Organization

The IndoorJSON conceptual hierarchy is preserved at the architectural level:

- `IndoorFeatures`
  - `ThematicLayer`
    - `PrimalSpaceLayer`
    - `DualSpaceLayer`
  - `InterLayerConnection`

In the database, layers function as **aggregation and scoping units**.  
Spatial entities and network elements are associated with their respective layers and are composed into hierarchical IndoorJSON structures at encoding time.

#### Topology and Connectivity

Topological relationships are represented using a combination of
normalized relational tables and application-level reference attributes.

- Network connectivity (Node–Edge relationships) and inter-layer
  connections are stored in **normalized relational tables**.
- Duality relationships are represented as **optional reference
  attributes** on individual elements and are applicable only to
  specific element types (e.g., `Node`).

Duality references may be null and are **not enforced as database foreign
keys**, but are validated and interpreted according to the IndoorGML
semantics at the application layer.

At response generation time, relational associations and reference
attributes are translated into their corresponding IndoorJSON
properties, including:

- `connects`
- inter-layer connection elements
- `duality`

This design minimizes storage redundancy while preserving **semantic
correctness and topological completeness** in the serialized IndoorJSON
output.

### Encoding Workflow

The generation of an IndoorJSON document follows a deterministic process:

1. Retrieve the IndoorFeatures root entity
2. Retrieve associated thematic layers
3. For each layer:
   - Assemble primal space members
   - Assemble dual space members
   - Resolve topological relationships
4. Assemble inter-layer connections
5. Serialize the result as a schema-conformant IndoorJSON document

### Design Considerations

The architecture is guided by the following objectives:

- **Standards compliance** with the IndoorJSON data model
- **Efficient spatial querying** using mature geospatial database technologies
- **Clear separation between storage schema and exchange schema**
- **Extensibility** for routing, overlays, and partial updates
- **Interoperability** with external IndoorGML- and OGC API–based systems

This design enables IndoorJSON to function as a **robust exchange format**, independent of the underlying persistence mechanism.

---

## 🛰 API Service Architecture

| Category | Endpoint | Description |
| :--- | :--- | :--- |
| **Core** | `/collections/{collection_id}/items/{feature_id}` | Standard OGC resource discovery and Feature access. |
| **IndoorFeature** | `.../layers/{layer_id}/...` | Specialized access to IndoorJSON components (Thematic layers). |
| **Navigation** | `...{layer_id}/routing` | Shortest path calculation powered by pgRouting.|
| **Spatial** | `/geoquery` | Advanced spatial filtering via WKT-form 2D geometries. |

💡 Tip: For a full list of over 20+ endpoints, including detailed parameter schemas and CRUD operations, please refer to our interactive documentation at:
🔗 Swagger UI: `/openapi`.

---

## 📥 Installation & Setup
### 1. Prerequisites
* Docker & Docker Compose (For PostGIS/pgRouting)
* Python 3.10+ (For pygeoapi)

### 2. Environment Startup
We recommend using a Python virtual environment to manage dependencies and avoid conflicts with system-level packages.
```bash
# Clone the repository
git clone [https://github.com/STEMLab/IndoorGML_API.git](https://github.com/STEMLab/IndoorGML_API.git)
cd IndoorGML_API
# Create and activate a Python Virtual Environment
python3 -m venv venv
source venv/bin/activate
# Install required dependencies
pip3 install -r requirements-indoor.txt
pip install -e .
# Start Docker Containers
docker-compose up -d --build
export PYGEOAPI_CONFIG=pygeoapi-config.yml
export PYGEOAPI_OPENAPI=local.openapi.yml
pygeoapi openapi generate $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI
pygeoapi serve
