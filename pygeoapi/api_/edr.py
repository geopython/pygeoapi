from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core'
]

conformance = ConformanceClasses(name='edr', classes=conformance_classes)
