from pygeoapi.api_ import ConformanceClasses


conformance_classes = [
    'http://www.opengis.net/spec/ogcapi-maps-1/1.0/conf/core'
]

conformance = ConformanceClasses(name='map', classes=conformance_classes)
