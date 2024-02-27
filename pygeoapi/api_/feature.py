from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/req/oas30',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson',
    'http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs',
    'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables',
    'http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/queryables-query-parameters',  # noqa
    'http://www.opengis.net/spec/ogcapi-features-5/1.0/conf/schemas',
    'http://www.opengis.net/spec/ogcapi-features-5/1.0/req/core-roles-features' # noqa
]

conformance = ConformanceClasses(name='feature', classes=conformance_classes)
