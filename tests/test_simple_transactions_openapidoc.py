from pygeoapi.openapi import get_oas_30

geoJSONdataPath = "tests/data/countries.geojson"

cfg = {
  "server": {
    "bind": {
      "host": "0.0.0.0",
      "port": 5000
    },
    "url": "http://localhost:5000/",
    "mimetype": "application/json; charset=UTF-8",
    "encoding": "utf-8",
    "language": "en-US",
    "pretty_print": True,
    "limit": 10,
    "map": {
      "url": "https://maps.wikimedia.org/osm-intl/{z}/{x}/{y}.png",
      "attribution": "<a href=\"https://wikimediafoundation.org/wiki/Maps_Terms_of_Use\">Wikimedia maps</a> | Map data &copy; <a href=\"https://openstreetmap.org/copyright\">OpenStreetMap contributors</a>"
    }
  },
  "logging": {
    "level": "ERROR"
  },
  "metadata": {
    "identification": {
      "title": "pygeoapi default instance",
      "description": "pygeoapi provides an API to geospatial data",
      "keywords": [
        "geospatial",
        "data",
        "api"
      ],
      "keywords_type": "theme",
      "terms_of_service": "https://creativecommons.org/licenses/by/4.0/",
      "url": "http://example.org"
    },
    "license": {
      "name": "CC-BY 4.0 license",
      "url": "https://creativecommons.org/licenses/by/4.0/"
    },
    "provider": {
      "name": "Organization Name",
      "url": "https://pygeoapi.io"
    },
    "contact": {
      "name": "Lastname, Firstname",
      "position": "Position Title",
      "address": "Mailing Address",
      "city": "City",
      "stateorprovince": "Administrative Area",
      "postalcode": "Zip or Postal Code",
      "country": "Country",
      "phone": "+xx-xxx-xxx-xxxx",
      "fax": "+xx-xxx-xxx-xxxx",
      "email": "you@example.org",
      "url": "Contact URL",
      "hours": "Mo-Fr 08:00-17:00",
      "instructions": "During hours of service. Off on weekends.",
      "role": "pointOfContact"
    }
  },
  "resources": {
    "countries": {
      "type": "collection",
      "title": "country",
      "description": "countries of the world",
      "keywords": [
        "countries"
      ],
      "links": [
        {
          "type": "text/html",
          "rel": "canonical",
          "title": "information",
          "href": "http://www.naturalearthdata.com/",
          "hreflang": "en-US"
        }
      ],
      "extents": {
        "spatial": {
          "bbox": [
            -180,
            -90,
            180,
            90
          ],
          "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
        },
        "temporal": {
          "begin": "2011-11-11T00:00:00.000Z",
          "end": None
        }
      },
      "provider": {
        "name": "GeoJSON",
        "data": geoJSONdataPath,
        "id_field": "id"
      }
    }
  }
}

postSchema = {
	'summary': 'Create country item',
	'description': 'countries of the world',
	'tags': ['countries'],
	'requestBody': {
		'required': True,
		'content': {
			'application/geo+json': {
				'schema': {
					'type': 'object',
					'properties': {
						'type': {
							'type': 'string',
							'enum': ['Feature']
						},
						'geometry': {
							'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/schemas/geometryGeoJSON'
						},
						'properties': {
							'type': 'object',
							'properties': {
								'name': {
									'type': 'string'
								},
								'featureclass': {
									'type': 'string'
								}
							}
						}
					}
				}
			}
		}
	},
	'responses': {
		201: {
			'description': 'Created country item',
			'headers': {
				'Location': {
					'schema': {
						'type': 'string'
					}
				}
			}
		},
		400: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/InvalidParameter'
		},
		404: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/NotFound'
		},
		500: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/ServerError'
		}
	}
}

patchSchema = {
	'summary': 'Update country item by id',
	'description': 'countries of the world',
	'tags': ['countries'],
	'parameters': [{
		'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/parameters/featureId'
	}],
	'requestBody': {
		'required': True,
		'content': {
			'application/json': {
				'schema': {
					'type': 'object',
					'properties': {
						'add': {
							'type': 'array',
							'items': {
								'$ref': '#/components/schemas/nameValuePairObj'
							}
						},
						'modify': {
							'type': 'array',
							'items': {
								'$ref': '#/components/schemas/nameValuePairObj'
							}
						},
						'remove': {
							'type': 'array',
							'items': {
								'type': 'string'
							}
						}
					}
				}
			}
		}
	},
	'responses': {
		200: {
			'description': 'Modified  country item',
			'headers': {
				'Location': {
					'schema': {
						'type': 'string'
					}
				}
			},
			'content': {
				'application/geo+json': {
					'schema': {
						'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/schemas/featureGeoJSON'
					}
				}
			}
		},
		400: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/InvalidParameter'
		},
		404: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/NotFound'
		},
		500: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/ServerError'
		}
	}
}

putSchema = {
	'summary': 'Replace country item by id',
	'description': 'countries of the world',
	'tags': ['countries'],
	'parameters': [{
		'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/parameters/featureId'
	}],
	'requestBody': {
		'required': True,
		'content': {
			'application/geo+json': {
				'schema': {
					'type': 'object',
					'properties': {
						'type': {
							'type': 'string',
							'enum': ['Feature']
						},
						'geometry': {
							'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/schemas/geometryGeoJSON'
						},
						'properties': {
							'type': 'object',
							'properties': {
								'name': {
									'type': 'string'
								},
								'featureclass': {
									'type': 'string'
								}
							}
						}
					}
				}
			}
		}
	},
	'responses': {
		200: {
			'$ref': '#/components/responses/200'
		},
		400: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/InvalidParameter'
		},
		404: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/NotFound'
		},
		500: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/ServerError'
		}
	}
}

deleteSchema = {
	'summary': 'Delete country item by id',
	'description': 'countries of the world',
	'tags': ['countries'],
	'parameters': [{
		'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/parameters/featureId'
	}],
	'responses': {
		200: {
			'$ref': '#/components/responses/200'
		},
		400: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/InvalidParameter'
		},
		404: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/NotFound'
		},
		500: {
			'$ref': 'http://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml#/components/responses/ServerError'
		}
	}
}

oas = get_oas_30(cfg)

def test_post():
    assert oas['paths']['/collections/countries/items']['post'] == postSchema

def test_patch():
    assert oas['paths']['/collections/countries/items/{featureId}']['patch'] == patchSchema

def test_put():
    assert oas['paths']['/collections/countries/items/{featureId}']['put'] == putSchema

def test_delete():
    assert oas['paths']['/collections/countries/items/{featureId}']['delete'] == deleteSchema