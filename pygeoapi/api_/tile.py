from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/mvt',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tileset',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/tilesets-list',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-tiles-1/1.0/conf/geodata-tilesets'
]

conformance = ConformanceClasses(name='tile', classes=conformance_classes)
