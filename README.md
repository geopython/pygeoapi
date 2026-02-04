# IndoorGML API

An expert-grade implementation of the **IndoorGML 2.0** conceptual model, designed to bridge **OGC API - Features** standards with complex indoor spatial analysis. This backend enables seamless transitions between physical space (Primal) and topological networks (Dual) for advanced indoor navigation.

---

## 🚀 Project Overview

This project provides a resource-oriented architecture for managing indoor spatial data. It leverages a high-performance **PostGIS/pgRouting** backend to support multi-layered indoor environments, ensuring compliance with international OGC standards.

### Key Accomplishments
* **OGC Standards Alignment:** Successfully mapped IndoorGML 2.0 resources to the OGC API - Features core.
* **Dual-Space Logic:** Full implementation of Primal Space (Rooms/Boundaries) and Dual Space (Nodes/Edges) connectivity.
* **Advanced Navigation:** Custom service endpoints for Shortest Path (Dijkstra) and Topological N-Hop analysis.
* **Engineering Precision:** Native support for **SRID 0** (Cartesian Plane) for building-scale accuracy.

---

## 🛠 Technical Pedigree

### Built on [pygeoapi](https://pygeoapi.io)
This engine is built upon a specialized fork of **pygeoapi**, a Python server implementation of the OGC API suite of standards. 
* **Standardized Access:** Provides RESTful endpoints using OpenAPI, GeoJSON, and HTML.
* **Extended Core:** We have customized the `api/indoorgml.py` core and developed custom providers to handle the unique hierarchy of `ThematicLayers` and `InterLayerConnections`.

### Persistence Layer
* **PostgreSQL/PostGIS:** Optimized schema for spatial bounding and geometric queries.
* **pgRouting:** Dynamic graph traversal without the overhead of static topology creation.
* **Dockerized:** Fully containerized environment for immediate deployment.

---

## 🗺 System Architecture

The system maintains a strict relationship between the physical environment and the logical navigation network:



1.  **IndoorFeatures:** The root container for building data.
2.  **Thematic Layers:** Separates physical layers (e.g., floors) from virtual layers (e.g., sensor coverage).
3.  **CellSpace (Primal):** 2D/3D geometries representing rooms.
4.  **State/Transition (Dual):** Nodes and Edges for pathfinding.

---

## 🛰 API Service Endpoints

| Category | Endpoint | Description |
| :--- | :--- | :--- |
| **Core** | `/collections` | OGC standard collection discovery. |
| **Navigation** | `/routing` | Shortest path calculation via pgRouting. |
| **Analysis** | `/connected` | Recursive N-Hop topological neighbor retrieval. |
| **Spatial** | `/geoquery` | Proximity and bounding box filtering. |

---

## 📥 Installation & Setup

### 1. Environment Startup
```bash
# Clone the repository
git clone [https://github.com/your-repo/indoorgml-backend.git](https://github.com/your-repo/indoorgml-backend.git)
cd indoorgml-backend

# Spin up the PostGIS and FastAPI containers
docker-compose up -d --build