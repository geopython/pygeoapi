from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/core',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/oas30',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/html',
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/geodata-coverage',  # noqa
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-subset',  # noqa
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-rangesubset',  # noqa
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-bbox',  # noqa
    'http://www.opengis.net/spec/ogcapi-coverages-1/1.0/conf/coverage-datetime'  # noqa
]

conformance = ConformanceClasses(name='coverage', classes=conformance_classes)
