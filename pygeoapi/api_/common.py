from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-common-2/1.0/conf/collections',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30'
]

conformance = ConformanceClasses(name='common', classes=conformance_classes)
