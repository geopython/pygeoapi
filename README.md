# pygeoapi

[![DOI](https://zenodo.org/badge/121585259.svg)](https://zenodo.org/badge/latestdoi/121585259)
[![Build](https://github.com/geopython/pygeoapi/actions/workflows/main.yml/badge.svg)](https://github.com/geopython/pygeoapi/actions/workflows/main.yml)
[![Docker](https://github.com/geopython/pygeoapi/actions/workflows/containers.yml/badge.svg)](https://github.com/geopython/pygeoapi/actions/workflows/containers.yml)
[![Vulnerabilities](https://github.com/geopython/pygeoapi/actions/workflows/vulnerabilities.yml/badge.svg)](https://github.com/geopython/pygeoapi/actions/workflows/vulnerabilities.yml)

[pygeoapi](https://pygeoapi.io) is a Python server implementation of the [OGC API](https://ogcapi.ogc.org) suite of standards. The project emerged as part of the next generation OGC API efforts in 2018 and provides the capability for organizations to deploy a RESTful OGC API endpoint using OpenAPI, GeoJSON, and HTML. pygeoapi is [open source](https://opensource.org/) and released under an [MIT license](https://github.com/geopython/pygeoapi/blob/master/LICENSE.md).

Please read the docs at [https://docs.pygeoapi.io](https://docs.pygeoapi.io) for more information.

# Speckle implementation of pygeoapi

## How to use Speckle data through OGC API Features

This is the test deployment of the OGC API server for public Speckle projects. It allows you to share your Speckle model as geospatial data in the format of OGC API Features / Web Feature Service, so it can be natively added to a QGIS, ArcGIS or Civil3D project, or embedded into a web map using Leaflet, OpenLayers or other libraries. 

Demo page: https://geo.speckle.systems/ 

### How to construct a valid URL to get georeferenced Speckle layer
URL should start with 'https://geo.speckle.systems/?' followed by required and optional parameters. Parameters should be separated with '&' symbol. You can use the generated link to access OGC API dataset in your preferred software, as well as explore the data in the browser and share with others. 

Use the following URL parameters to construct a link that provides Speckle data with your preferred settings::
 - speckleUrl (text), required, should contain path to a specific Model in Speckle Project, e.g. 'https://app.speckle.systems/projects/55a29f3e9d/models/2d497a381d'
 - dataType (text), optional, choose from: points, lines, polygons or projectcomments
 - limit (positive integer), recommended, as some applications might apply their custom feature limit
 - preserveAttributes (string), optional, choose from: true, false. If not set, meshes will be split into separate polygons for better display quality.
 - crsAuthid (text), an authority string e.g. 'epsg:4326'. If set, LAT, LON and NORTHDEGREES arguments will be ignored.
 - lat (number), in range -90 to 90
 - lon (number), in range -180 to 180
 - northDegrees (number), in range -180 to 180
If GIS-originated Speckle model is loaded, no location arguments are needed.  

Example: [https://geo.speckle.systems/?speckleUrl=https://app.speckle.systems/projects/64753f52b7/models/338b386787&lat=-0.031405&lon=109.335828](https://geo.speckle.systems/?speckleUrl=https://app.speckle.systems/projects/64753f52b7/models/338b386787&lat=-0.031405&lon=109.335828)


### Add Speckle Feature Layer to a web-based map

Check out the examples in 'speckle_demos' folder for Leaflet and OpenLayers implementation.

### Add Speckle WFS layer in QGIS
1. Add new WFS Layer

![image](https://github.com/user-attachments/assets/ea168853-dc97-43bf-b9f2-4d0244addb01)

2. Create New connection, specify the name and URL with mandatory "speckleUrl" parameter pointing to the Speckle Model. Then click Detect, and the WFS Version should display "OGC API Features". Click OK.

![image](https://github.com/user-attachments/assets/8bf9f164-bdb1-455e-8298-f0c1d5dd324d)

3. Connect, select the dataset "Speckle data" and click "Add".

![image](https://github.com/user-attachments/assets/73c97729-f3b3-4192-a4cf-667ba147fc6f)

4. Loading of the data might take a minute, then you will be able to Zoom to layer and check the Attribute table. Done! 

![image](https://github.com/user-attachments/assets/0708c64e-b063-4f55-b9f4-e791fc32da95)


### Add Speckle OGC API layer in ArcGIS

TODO


### Add Speckle WFS layer in Civil3D

TODO

## Local dev
First launch:
```python
python -m venv pygeoapi_venv
cd pygeoapi_venv
Scripts\activate
cd pygeoapi
git clone https://github.com/specklesystems/pygeoapi
git checkout dev
pip install --upgrade pip
pip install -r requirements.txt
python -m pip install --upgrade specklepy==2.19.6
python -m pip install pydantic==1.10.17
python pygeoapi\provider\speckle_utils\patch\patch_specklepy.py
python setup.py install
set PYGEOAPI_CONFIG=example-config.yml // export
set PYGEOAPI_OPENAPI=example-config.yml // export
set MAPTILER_KEY_LOCAL=your_api_key // export, (if available)
pygeoapi openapi generate $PYGEOAPI_CONFIG > $PYGEOAPI_OPENAPI
pygeoapi serve
```

Repeated launch:
```python
cd pygeoapi_venv
Scripts\activate
cd pygeoapi
python -m pip install --upgrade specklepy==2.19.6
python -m pip install pydantic==1.10.17
python pygeoapi\provider\speckle_utils\patch\patch_specklepy.py
python setup.py install
set PYGEOAPI_CONFIG=example-config.yml
set PYGEOAPI_OPENAPI=example-config.yml
set MAPTILER_KEY_LOCAL=your_api_key
pygeoapi openapi generate $PYGEOAPI_CONFIG > $PYGEOAPI_OPENAPI
pygeoapi serve

```

