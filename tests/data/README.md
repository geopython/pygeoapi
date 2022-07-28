# Test Data

This directory provides test data to demonstrate functionality.

## Sources

### `ne_110m_lakes.geojson and tiles/ne_110m_lakes`

- source: Natural Earth Lakes + Reservoirs
- URL: [https:/naturalearthdata.com/downloads/110m-physical-vectors/110mlakes-reservoirs/](https://naturalearthdata.com/downloads/110m-physical-vectors/110mlakes-reservoirs/)
- Shapefile converted to GeoJSON.  Tiles created with tippecanoe
- Made with Natural Earth. Free vector and raster map data @ [naturalearthdata.com](https://naturalearthdata.com)

### `ne_110m_admin_0_countries.sqlite`

- source: Natural Earth Admin 0 - Countries
- URL: [https://naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/](https://naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/)
- Shapefile converted to SQLite
- Made with Natural Earth. Free vector and raster map data @ [naturalearthdata.com](https://naturalearthdata.com)

### `ne_110m_populated_places_simple.geojson`

- source: Natural Earth Populated Places
- URL: [https://naturalearthdata.com/downloads/110m-cultural-vectors/110m-populated-places/](https://naturalearthdata.com/downloads/110m-cultural-vectors/110m-populated-places/)
- Shapefile converted to GeoJSON
- Made with Natural Earth. Free vector and raster map data @ [naturalearthdata.com](https://naturalearthdata.com)

### `obs.csv`

- source: MapServer msautotest suite
- URL: [https://github.com/mapserver/mapserver/blob/branch-7-0/msautotest/wxs/data/obs.csv](https://github.com/mapserver/mapserver/blob/branch-7-0/msautotest/wxs/data/obs.csv)
- Copyright (c) 2008-2018 Open Source Geospatial Foundation
- Copyright (c) 1996-2008 Regents of the University of Minnesota

### `poi_portugal.gpkg`

- source: OpenStreetMap - Natural GIS
- URL: [https://naturalgis.pt/cgi-bin/opendata/mapserv?service=WFS&request=GetCapabilities](https://www.naturalgis.pt/cgi-bin/opendata/mapserv?service=WFS&request=GetCapabilities)
- Data obtained from WFS instance of NaturalGIS company (https://naturalgis.pt/en/) and converted to geopackage
- Upstream data from OpenStreetMap extract for Portugal

### `hotosm_bdi_waterways.sql.gz`

- source: OpenStreetMap - Humanitarian OpenStreetMap Team (HOT)
- URL: [hotosm_bdi_waterways](https://data.humdata.org/dataset/hotosm_bdi_waterways)
- Waterways of Burundi
- Date of dataset: Sep 01, 2018
- Location: Burundi, Africa

### `CMC_glb_*.grib2`

- source: [Meteorological Service of Canada Datamrt](https://eccc-msc.github.io/open-data/msc-datamart/readme_en)
- URL: https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/00/000
- License: https://eccc-msc.github.io/open-data/licence/readme_en

### `CMIP5_rcp8.5_annual_abs_latlon1x1_PCP_pctl25_P1Y.nc`

- source: [Canadian Centre for Climate Services](https://canada.ca/climate-services)
- URL: https://dd.weather.gc.ca/climate/cmip5/netcdf/scenarios/RCP8.5/annual/absolute/CMIP5_rcp8.5_annual_abs_latlon1x1_PCP_pctl25_P1Y.nc
- License: https://eccc-msc.github.io/open-data/licence/readme_en

### `coads_sst.nc`

- source: [NOAA Physical Sciences Library](https://psl.noaa.gov)
- URL: https://psl.noaa.gov/data/gridded/data.coads.1deg.html
- License: ICOADS data provided by the NOAA/OAR/ESRL PSL, Boulder, Colorado, USA, from their Web site at https://psl.noaa.gov.

### `analysed_sst.nc`
- source: [NASA Physical Oceanography Distributed Active Archive Center](https://podaac.jpl.nasa.gov)
- URL: https://registry.opendata.aws/mur
- License: https://registry.opendata.aws/mur/#License

### `open.canada.ca/sample-records.tinydb`

- source: Open Data Canada
- URL: https://csw.open.canada.ca/geonetwork/srv/csw?service=CSW&version=2.0.2&request=GetRecords&outputschema=http://www.isotc211.org/2005/gmd&resulttype=results (2021-02-18)
- License: https://www.canada.ca/en/transparency/terms.html
- Notes
  - ISO records transformed to OGC API - Records GeoJSONs with `tests/load_tinydb_records.py`

### `dutch_addresses_*`
- source: Dutch Kadaster
- URL: https://geodata.nationaalgeoregister.nl/inspireadressen/wfs?request=GetCapabilities&service=wfs (discontinued, see below)
- License: CC0 1.0 https://creativecommons.org/publicdomain/zero/1.0/deed.nl
- Notes
  - above WFS [was switched off in June 2022](https://www.pdok.nl/-/oude-url-s-inspire-adressen-uitgefaseerd)
  - address-records derived by Kadaster from the Dutch "Buildings and Addresses" key registry (BAG)
  - WMS is still available: https://service.pdok.nl/kadaster/adressen/wms/v1_0?request=GetCapabilities&service=WMS
  - raw dataset BAG (GML, about 2GB) can always be downloaded via the [Atom Feed](https://service.pdok.nl/kadaster/adressen/atom/v1_0/index.xml)

### `items.geojson`
- source: Wikipedia
- URL: https://en.wikipedia.org/wiki/GeoJSON#Geometries
- License: CC0 3.0 https://creativecommons.org/licenses/by-sa/3.0/
- Notes
  - `items.geojson` tests pygeoapi's capability to serialize all geometry types for individual collection items in [JSON-LD formats](https://docs.pygeoapi.io/en/latest/configuration.html#linked-data), including GeoSPARQL WKT and schema.org/geo.
  - The features represent the range of geoJSON geometry types, instead of real locations. Additionally, each feature has a uri defined in the properties block.
