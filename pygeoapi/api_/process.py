from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description', # noqa
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json',
    'http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/oas30'
]

conformance = ConformanceClasses(name='process', classes=conformance_classes)
