# =================================================================
#
# Authors: Richard Law <lawr@landcareresearch.co.nz>
#
# Copyright (c) 2020 Richard Law
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the 'Software'), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import datetime
from itertools import repeat
import logging
from numbers import Number

from pyproj import CRS
from pyproj.transformer import Transformer, AreaOfInterest, TransformerGroup
from pyproj.enums import WktVersion, TransformDirection
from shapely import wkt
from shapely.geometry import Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection
from shapely.ops import transform

from pygeoapi.process.base import BaseProcessor

LOGGER = logging.getLogger(__name__)
CURRENT_YEAR = float(datetime.datetime.now().year)

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.0.1',
    'id': 'wkt-reprojector',
    'title': 'WKT Reprojector',
    'description': 'An example process that reprojects a geometry from one CRS to another, using PROJ v6. This will take account of possible datum shifts. Because of the use of PROJ v6, late-binding can be used, and 4D coordinates (three spatial components and one temporal component) are supported.',
    'keywords': ['reprojection', 'PROJ', '2D', '3D', '4D', 'spatiotemporal transformation'],
    'links': [{
        'type': 'text/html',
        'rel': 'related',
        'title': 'pyproj Documentation',
        'href': 'https://pyproj4.github.io/pyproj/stable/',
        'hreflang': 'en'
    }],
    'inputs': [{
        'id': 'wkt',
        'title': 'WKT representation of the input geometry',
        'abstract': 'Well-known text (WKT) representation of the input geometry. M-values will be ignored, e.g. a <span style="font-family:monospace;">POINT ZM</span> will be converted to a <span style="font-family:monospace;">POINT Z</span> due to <a href="https://github.com/Toblerity/Shapely/issues/882" target="#">current limitations</a> of Shapely. This also means that <span style="font-family:monospace;">POINT M</span>, <span style="font-family:monospace;">LINESTRING M</span>, etc. should be used with care since they will be interpreted as <span style="font-family:monospace;">POINT Z</span>, <span style="font-family:monospace;">LINESTRING Z</span>, etc. If you use M to represent time, use the <span style="font-family:monospace;">time</span> parameter to capture the epoch in order to perform 4D transformation.',
        'input': {
            'literalDataDomain': {
                'dataType': 'string',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': 'MULTIPOLYGON (((40 40, 20 45, 45 30, 40 40)), ((20 35, 10 30, 10 10, 30 5, 45 20, 20 35), (30 20, 20 15, 20 25, 30 20)))'
                }
            }
        },
        'minOccurs': 1,
        'maxOccurs': 1,
        'metadata': None,
        'keywords': ['WKT', 'geometry']
    }, {
        'id': 'time',
        'title': 'Time (decimal year)',
        'abstract': 'To support time-dependent datum transformations, given that the M-coordinate of the WKT input will be ignored, the time for the transformation should be specified with this parameter (as a decimal year, e.g. 2020.0). This M-value will be assumed for all vertices of the geometry.',
        'input': {
            'literalDataDomain': {
                'dataType': 'float',
                'valueDefinition': {
                    'anyvalue': False,
                    'defaultValue': CURRENT_YEAR
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'metadata': None,
        'keywords': ['time', '4D transformation']
    }, {
        'id': 'src_crs',
        'title': 'Source CRS',
        'abstract': 'The input coordinate reference system (CRS), with a known identifier, or an OGC WKT string.',
        'input': {
            'literalDataDomain': {
                'dataType': 'string',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': 'EPSG:4326'
                }
            }
        },
        'minOccurs': 1,
        'maxOccurs': 1,
        'keywords': ['CRS', 'PROJ']
    }, {
        'id': 'dst_crs',
        'title': 'Destination CRS',
        'abstract': 'The output coordinate reference system (CRS), with a known identifier, or an OGC WKT string.',
        'input': {
            'literalDataDomain': {
                'dataType': 'string',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': "EPSG:3857"
                }
            }
        },
        'minOccurs': 1,
        'maxOccurs': 1,
        'keywords': ['CRS', 'PROJ']
    }, {
        'id': 'always_xy',
        'title': 'Force x,y axis order',
        'abstract': 'If this is false, axis order may be swapped relative to the input WKT geometry, if the source and destination CRSs are defined as the having the first coordinate component point in a northerly direction. See <a target="#" href="http://pyproj4.github.io/pyproj/stable/api/transformer.html?highlight=always_xy">pyproj documentation</a> for more information.',
        'input': {
            'literalDataDomain': {
                'dataType': 'boolean',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': False
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['axis order']
    }, {
        'id': 'errcheck',
        'title': 'Error checking',
        'abstract': 'If True, the result is an error if the transformation is invalid. By default this is False and an invalid transformation returns inf for coordinate values yet the result is considered successful.',
        'input': {
            'literalDataDomain': {
                'dataType': 'boolean',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': True
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['validation']
    }, {
        'id': 'best_available',
        'title': 'Require best transformation',
        'abstract': 'Require the best possible transformation to be applied; if it cannot be applied due to missing grids in this service, the result will be an error rather than an inferior output.',
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['validation'],
        'input': {
            'literalDataDomain': {
                'dataType': 'boolean',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': True
                }
            }
        }
    }, {
        'id': 'radians',
        'title': 'Radians input',
        'abstract': 'If True, will expect input data to be in radians and will return radians if the projection is geographic. Default is False (degrees). Ignored for pipeline transformations.',
        'input': {
            'literalDataDomain': {
                'dataType': 'boolean',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': False
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['radians','degrees','input']
    }, {
        'id': 'direction',
        'title': 'Transformation direction',
        'abstract': 'The direction of the transform.',
        'input': {
            'literalDataDomain': {
                'dataType': 'enum',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': TransformDirection.FORWARD.value,
                    'possibleValues': list(map(lambda _: _.value, TransformDirection))
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['transformation direction']
    }, {
        'id': 'rounding_precision',
        'title': 'Output coordinate precision',
        'abstract': 'The desired rounding precision of output coordinates, in decimal places. The default is five decimal places. The minimum value is 0. <a target="#" href="https://www.xkcd.com/2170/">xkcd</a> has a helpful guide.',
        'input': {
            'literalDataDomain': {
                'dataType': 'integer',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': 5
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['coordinate precision','precision']
    }, {
        'id': 'minimum_accuracy',
        'title': 'Acceptable loss of accuracy',
        'abstract': 'Transformations usually have an expected accuracy, and not all transformations can promise to introduce no new error (before considering floating point or rounding errors). This parameter allows you to control the acceptable level of accuracy lost: if the expected accuracy degradation is more than this value (or if it is unknown), specified in metres, the result will be an error and the transformation will not be performed. If this parameter is absent or null, the transformation will always proceed.',
        'input': {
            'literalDataDomain': {
                'dataType': 'float',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': None
                }
            }
        },
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['accuracy','error']
    },{
        'id': 'west_lon_degree',
        'title': 'Area of interest (western extent)',
        'abstract': 'The west bound in degrees of the area of interest. All four area of interest parameters must be specified for this to take effect.',
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['area of interest','longitude'],
        'input': {
            'literalDataDomain': {
                'dataType': 'float',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': None
                }
            }
        }
    }, {
        'id': 'south_lat_degree',
        'title': 'Area of interest (southern extent)',
        'abstract': 'The south bound in degrees of the area of interest. All four area of interest parameters must be specified for this to take effect.',
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['area of interest','latitude'],
        'input': {
            'literalDataDomain': {
                'dataType': 'float',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': None
                }
            }
        }
    }, {
        'id': 'east_lon_degree',
        'title': 'Area of interest (eastern extent)',
        'abstract': 'The east bound in degrees of the area of interest. All four area of interest parameters must be specified for this to take effect.',
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['area of interest','longitude'],
        'input': {
            'literalDataDomain': {
                'dataType': 'float',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': None
                }
            }
        }
    }, {
        'id': 'north_lat_degree',
        'title': 'Area of interest (northern extent)',
        'abstract': 'The north bound in degrees of the area of interest. All four area of interest parameters must be specified for this to take effect.',
        'minOccurs': 0,
        'maxOccurs': 1,
        'keywords': ['area of interest','latitude'],
        'input': {
            'literalDataDomain': {
                'dataType': 'float',
                'valueDefinition': {
                    'anyValue': False,
                    'defaultValue': None
                }
            }
        }
    }],
    'outputs': [{
        'id': 'wkt',
        'title': 'Reprojected geometry',
        'description': 'A geometry that has been transformed into the destination CRS',
        'output': {
            'literalDataDomain': {
                'dataType': {
                    'name': 'string'
                },
                'valueDefinition': {
                    'anyValue': True
                }
            }
        }
    }, {
        # 'id': 'src_crs',
        # 'title': 'Source CRS (PROJJSON)',
        # 'description': 'A PROJJSON representation of the source CRS, useful for verifying that the input CRS was correctly interpreted.',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        # 'id': 'dst_crs',
        # 'title': 'Destination CRS (PROJJSON)',
        # 'description': 'A PROJJSON representation of the destination CRS, useful for verifying that the input CRS was correctly interpreted.',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        # 'id': 'accuracy',
        # 'title': 'Accuracy',
        # 'description': 'Operation accuracy is an optional attribute which indicates the typical error the application of the coordinate operation has introduced into the transformed target CRS coordinates, assuming input of errorless source CRS coordinates. It is an approximate figure for the area of applicability of the coordinate operation as a whole, given in metres.',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'float'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        'id': 'definition',
        'title': 'Projection definition',
        'description': 'Definition of the applied transformation',
        'output': {
            'literalDataDomain': {
                'dataType': {
                    'name': 'string'
                },
                'valueDefinition': {
                    'anyValue': True
                }
            }
        }
    }, {
        # 'id': 'description',
        # 'title': 'Projection description',
        # 'description': 'Description of the applied transformation',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        # 'id': 'name',
        # 'title': 'Projection name',
        # 'description': 'Name of the applied transformation',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        # 'id': 'remarks',
        # 'title': 'Transformation remarks',
        # 'description': 'Optional remarks about the applied transformation',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        # 'id': 'scope',
        # 'title': 'Transformation scope',
        # 'description': 'Scope of the applied projection',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        # 'id': 'transformer_wkt',
        # 'title': 'Transformation WKT string',
        # 'description': 'The transformation represented as a well-known text (WKT2 2019) string',
        # 'output': {
        #     'literalDataDomain': {
        #         'dataType': {
        #             'name': 'string'
        #         },
        #         'valueDefinition': {
        #             'anyValue': True
        #         }
        #     }
        # }
    }, {
        'id': 'transformer',
        'title': 'Transformation ',
        'description': 'The applied transformation represented as JSON object, including the source CRS, target CRS, transformation description, scope, etc.',
        'output': {
            'literalDataDomain': {
                'dataType': {
                    'name': 'string'
                },
                'valueDefinition': {
                    'anyValue': True
                }
            }
        }
    }, {
        'id': 'best_available',
        'title': 'Application of best available transformation',
        'description': 'Boolean indicating whether the best available transformation was applied (true) or not (false). In the latter case, this may be because the server was missing an optimal grid to perform the requested transformation. Use the "best_available" input parameter to control whether the projection should still proceed if the best available transformation is not available.',
        'output': {
            'literalDataDomain': {
                'dataType': {
                    'name': 'boolean'
                },
                'valueDefinition': {
                    'anyValue': False
                }
            }
        }
    }],
    'example': {
        'inputs': [
        {
            'id': 'wkt',
            'value': 'MULTIPOLYGON (((40 40, 20 45, 45 30, 40 40)), ((20 35, 10 30, 10 10, 30 5, 45 20, 20 35), (30 20, 20 15, 20 25, 30 20)))',
            'type': 'text/plain'
        }, {
            'id': 'src_crs',
            'value': 'EPSG:4326',
            'type': 'text/plain'
        }, {
            'id': 'dst_crs',
            'value': "EPSG:3857",
            'type': 'text/plain'
        }, {
            'id': 'always_xy',
            'value': True
        }, {
            'id': 'best_available',
            'value': True
        }, {
            'id': 'west_lon_degree',
            'value': -180.0
        }, {
            'id': 'south_lat_degree',
            'value': -90.0
        }, {
            'id': 'east_lon_degree',
            'value': 180.0
        }, {
            'id': 'north_lat_degree',
            'value': 90.0
        }, {
            'id': 'rounding_precision',
            'value': 5
        }]
    }
}

class BestTransformationUnavailableError(Exception):
    """
    Raise when the transformation is limited to using the best possible
    transformation, but this is not available due to missing grids
    """
    def __init__(self, message, best_transformation, *args):
        self.message = message
        self.best_transformation = best_transformation
        super(MyAppValueError, self).__init__(message, best_transformation, *args)

class TransformationUnavailableError(Exception):
    """
    Raise when there is no identified transformation between two CRSs
    """
    def __init__(self, input_crs, output_crs, *args):
        self.input_crs = input_crs
        self.output_crs = output_crs
        message = f'There is no transformation between {self.input_crs.name} and {self.output_crs.name}'
        self.message = message
        super(MyAppValueError, self).__init__(message, input_crs, output_crs, *args)

class TooInaccurateError(Exception):
    """
    Raise when the transformation accuracy is too high relative to client
    expectation
    """
    def __init__(self, message, accuracy, *args):
        self.message = message
        self.accuracy = best_transformation
        super(MyAppValueError, self).__init__(message, accuracy, *args)

def geom_transformation(transformer, geom, params):
    LOGGER.debug(geom.type)
    if geom.type == 'GeometryCollection':
        collection = [geom_transformation(transformer, _geom, params) for _geom in geom.geoms]
        geom_output = GeometryCollection(collection)
    elif not geom.type.startswith('Multi'):
        geom_output = singlepart_geom_transformation(transformer, geom, params)
    elif geom.type.startswith('Multi'):
        parts = [geom_transformation(transformer, part, params) for part in geom]
        if parts[0].type == 'Point':
            geom_output = MultiPoint(parts)
        elif parts[0].type == 'LineString':
            geom_output = MultiLineString(parts)
        elif parts[0].type == 'Polygon':
            geom_output = MultiPolygon(parts)
    return geom_output

def singlepart_geom_transformation(transformer, geom, params):
    LOGGER.debug('Performing singlepart geometry transformation')
    trans_kwargs = {
        'radians': params['radians'],
        'errcheck': params['errcheck'],
        'direction': params['direction']
    }
    if hasattr(geom, 'type') and geom.type == 'Polygon':
        LOGGER.debug('Polygon type: transforming in rings')
        LOGGER.debug(geom.exterior)
        LOGGER.debug(geom.interiors)
        shell = singlepart_geom_transformation(transformer, geom.exterior, params)
        holes = [singlepart_geom_transformation(transformer, hole, params) for hole in geom.interiors]
        return Polygon(shell, holes=holes)
    print(geom)
    trans_kwargs = {
        'tt': tuple([float(params.get('time'))]) * len(geom.coords),
        **trans_kwargs
    }
    if not geom.has_z:
        # GEOS does not understand M, but to allow for time-dependent
        # transformations, M must be used to represent time, and then
        # removed from the output - because GEOS re-interprets M as Z
        # see https://github.com/Toblerity/Shapely/issues/882
        geom_slice = slice(2)
        coord_transformer = lambda xx, yy: transformer.transform(xx, yy,
            zz=None,
            **trans_kwargs
        )[geom_slice]
        return transform(coord_transformer, geom)
    # Input is 3-dimensional (X, Y, Z), or
    # Input has M (X, Y, M) - M will be interpreted as Z
    # In the case of ZM: M is silently dropped by GEOS, Z is retained
    # Therefore, POINT M (1 2 3) is interpreted as POINT Z (1 2 3)
    # and POINT ZM (1 2 3 4) is interpreted as POINT Z (1 2 3)
    # and this limitation is regretfully acknowledged
    geom_slice = slice(3)
    coord_transformer = lambda xx, yy, zz: transformer.transform(xx, yy,
        zz=zz,
        **trans_kwargs
    )[geom_slice]
    return transform(coord_transformer, geom)

class WKTReprojectorProcessor(BaseProcessor):
    '''WKT reprojection example'''

    def __init__(self, provider_def):
        '''
        Initialize object
        :param provider_def: provider definition
        :returns: pygeoapi.process.reproject-coords.WKTReprojectorProcessor
        '''
        # Filter out empty outputs
        metadata = dict(PROCESS_METADATA)
        metadata['outputs'] = list(filter(bool,metadata['outputs']))

        BaseProcessor.__init__(self, provider_def, metadata)

    def execute(self, data):
        wkt_input = data.get('wkt', self.get_default('wkt'))
        geom = wkt.loads(wkt_input)
        params = {p: data.get(p, self.get_default(p)) for p in (
            'always_xy', 'errcheck', 'radians', 'direction', 'src_crs', 'dst_crs',
            'best_available', 'rounding_precision', 'time', 'minimum_accuracy'
        )}
        aoi_params = ('west_lon_degree','south_lat_degree','east_lon_degree','north_lat_degree')
        if all(map(lambda b: isinstance(data.get(b, None), Number), aoi_params)):
            params['area_of_interest'] = AreaOfInterest(*map(data.get, aoi_params))
        input_crs = CRS.from_user_input(params.get('src_crs').strip())
        output_crs = CRS.from_user_input(params.get('dst_crs').strip())

        transformerGroup = TransformerGroup(
            crs_from=input_crs,
            crs_to=output_crs,
            skip_equivalent=True, # Don't perform a transformation between equivalent CRSs
            always_xy=params.get('always_xy'),
            area_of_interest=params.get('area_of_interest', None)
        )
        if not len(transformerGroup.transformers):
            raise TransformationUnavailableError(input_crs, output_crs)
        if params.get('best_available') and not transformerGroup.best_available:
            raise BestTransformationUnavailableError(f'Transformation {transformer.unavailable_operations[0].name} is unavailable', transformer.unavailable_operations[0])
        elif transformerGroup.best_available:
            is_best_available = True
        else:
            is_best_available = False
        transformer = transformerGroup.transformers[0]
        minimum_accuracy = params.get('minimum_accuracy')
        if minimum_accuracy is not None and transformer.accuracy > minimum_accuracy:
            raise TooInaccurateError(f'The transformation would introduce too much inaccuracy in the output ({transformer.accuracy} > {minimum_accuracy})', transformer.accuracy)
        rounding_precision = max(0, int(params.get('rounding_precision')))
        kwargs = {
            'radians': params['radians'],
            'errcheck': params['errcheck'],
            'direction': params['direction']
        }
        LOGGER.debug(geom.type)
        geom_output = geom_transformation(transformer, geom, params)
        wkt_geom = wkt.dumps(geom_output, rounding_precision=rounding_precision).replace('"','')
        if not geom.has_z and geom_output.has_z:
            wkt_geom = wkt_geom.replace('Z', 'M')
            LOGGER.debug('Replaced false Z with M')
        LOGGER.debug(wkt_geom)
        return {
            'wkt': wkt_geom,
            # 'src_crs': input_crs.to_json_dict(),#.to_wkt(version=WktVersion.WKT2_2019, pretty=False),
            # 'dst_crs': output_crs.to_json_dict(),#.to_wkt(version=WktVersion.WKT2_2019, pretty=False),
            # 'area_of_use': {
            #     'west': transformer.area_of_use.west,
            #     'south': transformer.area_of_use.south,
            #     'east': transformer.area_of_use.east,
            #     'north': transformer.area_of_use.north,
            #     'name': transformer.area_of_use.name
            # },
            # 'accuracy': float(transformer.accuracy) if transformer.accuracy != -1 else None,
            'definition': transformer.definition,
            # 'description': transformer.description,
            # 'name': transformer.name,
            # 'remarks': transformer.remarks,
            # 'scope': transformer.scope,
            'transformer': transformer.to_json_dict(),
            # 'transformer_wkt': transformer.to_wkt(version=WktVersion.WKT2_2019),
            'best_available': is_best_available,
            'is_bound': output_crs.is_bound,
            'is_engineering': output_crs.is_engineering,
            'is_geocentric': output_crs.is_geocentric,
            'is_geographic': output_crs.is_geographic,
            'is_projected': output_crs.is_projected,
            'is_vertical': output_crs.is_vertical
        }

    def __repr__(self):
        return '<WKTReprojectorProcessor> {}'.format(self.name)
