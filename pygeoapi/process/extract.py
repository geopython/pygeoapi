# =================================================================
#
# Authors: Alexandre Roy <alexandre.roy@nrcan-rncan.gc.ca>
#
# Copyright (c) 2023 Alexandre Roy
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import logging
from pygeoapi.process.base import BaseProcessor
from pygeoapi.provider.base import ProviderPreconditionFailed
from pygeoapi.util import get_provider_by_type
from pygeoapi.plugin import load_plugin

LOGGER = logging.getLogger(__name__)

#: Process metadata and description
PROCESS_METADATA = {
    'version': '0.2.0',
    'id': 'extract',
    'title': {
        'en': 'Extract the data',
        'fr': 'Extrait les données'
    },
    'description': {
        'en': 'This process takes a list of collections, a geometry wkt and crs as inputs and proceeds to extract the records of all collections.',  # noqa
        'fr': 'Ce processus prend une liste de collections, une géométrie en format wkt avec un crs et extrait les enregistrements de toutes les collections.',  # noqa
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': ['extract'],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'information',
        'href': 'https://example.org/process',
        'hreflang': 'en-US'
    }],
    'inputs': {
        'collections': {
            'title': 'An array of collection names to extract records from',
            'description': 'An array of collection names to extract records from',  # noqa
            'schema': {
                'type': 'string'
            },
            'minOccurs': 1,
            'maxOccurs': 99,
            'metadata': None,  # TODO how to use?
            'keywords': ['collections', 'records']
        },
        'geom': {
            'title': 'The geometry as WKT format',
            'description': 'The geometry as WKT format',
            'schema': {
                'type': 'string'
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,
            'keywords': ['geometry']
        },
        'geom_crs': {
            'title': 'The crs of the input geometry',
            'description': 'The crs of the input geometry',
            'schema': {
                'type': 'integer'
            },
            'minOccurs': 1,
            'maxOccurs': 1,
            'metadata': None,
            'keywords': ['crs']
        }
    },
    'outputs': {
        'echo': {
            'title': 'The url to the zip file containing the information',
            'description': 'The url to the zip file containing the information',  # noqa
            'schema': {
                'type': 'object',
                'contentMediaType': 'application/json'
            }
        }
    },
    'example': {
        'inputs': {
            "collections": [
                "coll_name_1",
                "coll_name_2"
            ],
            "geom": "POLYGON((-72.3061 45.3656, -72.3061 45.9375, -71.7477 45.9375, -71.7477 45.3656, -72.3061 45.3656))",  # noqa
            "geom_crs": 4326
        }
    }
}


class ExtractProcessor(BaseProcessor):
    """
    Extract Processor used to query multiple collections, of various
    providers, at the same time. In this iteration, only collection types
    feature and coverage are supported, but the logic could be scaled up.
    """

    def __init__(self, processor_def, process_metadata):
        """
        Initialize the Extract Processor

        :param processor_def: provider definition
        :param process_metadata: process metadata

        :returns: pygeoapi.process.extract.ExtractProcessor
        """

        # If none set, use default
        if not process_metadata:
            process_metadata = PROCESS_METADATA

        super().__init__(processor_def, process_metadata)
        self.colls = None
        self.geom_wkt = None
        self.geom_crs = None

    def get_collection_type(self, coll_name: str):
        """
        Return the collection type given its collection name by reading the
        internal processor definition configuration.

        :param coll_name: the collection name

        :returns: the collection type
        """

        # Read the configuration for it
        c_conf = self.processor_def['collections'][coll_name]

        # Get the collection type by its providers
        return self._get_collection_type_from_providers(c_conf['providers'])

    def get_collection_coverage_mimetype(self, coll_name: str):
        """
        Return the collection coverage mimetype given its collection name
        by reading the internal processor definition configuration.

        :param coll_name: the collection name

        :returns: the collection coverage mimetype
        """

        # Read the configuration for it
        c_conf = self.processor_def['collections'][coll_name]

        # Get the collection type by its providers
        return self._get_collection_mimetype_image_from_providers(
            c_conf['providers'])

    def execute(self, data: dict):
        """
        Entry point of the execution process.

        :param data: the input parameters, as-received, for the process

        :returns: results of the process as provided by 'on_query_results'
        """

        try:
            # Validate inputs
            if self.on_query_validate_inputs(data):
                # Validate execution
                if self.on_query_validate_execution(data):
                    # For each collection to query
                    query_res = {}
                    i = 1
                    message = "Collections:\n"
                    for c in self.colls:
                        # If running inside a job manager
                        if self.process_manager:
                            # The progression can be a value between 15 and 85
                            # (<10 and >90 reserved by the process manager
                            # itself)
                            prog_value = ((85 - 15) * i / len(self.colls)) + 15  # noqa
                            message = message + (" | " if i > 1 else "") + c

                            # Update the job progress
                            self.process_manager.update_job(
                                self.job_id, {
                                    'message': message,
                                    'progress': prog_value
                                })

                        # Call on query with it which will query the
                        # collection based on its provider
                        query_res[c] = self.on_query(c,
                                                     self.geom_wkt,
                                                     self.geom_crs)

                        # Increment
                        i = i+1

                    # Finalize the results
                    self.on_query_finalize(data, query_res)

                    # Return result
                    return self.on_query_results(query_res)

                else:
                    raise ProviderPreconditionFailed("Invalid execution parameters")  # noqa

            else:
                raise ProviderPreconditionFailed("Invalid input parameters")

        except Exception as err:
            # Call on exception
            self.on_exception(err)

            # Keep raising error
            raise err

    def on_query(self, coll_name: str, geom_wkt: str, geom_crs: int):
        """
        Overridable function to query a particular collection given its name.

        :param coll_name: the collection name to extract, validated
        :param geom_wkt: the geometry wkt, validated
        :param geom_crs: the geometry crs, validated

        :returns: results of the process as provided by 'on_query_results'
        """

        # Read the configuration for it
        c_conf = self.processor_def['collections'][coll_name]

        # Get the collection type by its providers
        c_type = self._get_collection_type_from_providers(c_conf['providers'])

        # Get the provider by type
        provider_def = get_provider_by_type(c_conf['providers'], c_type)

        # Load the plugin
        p = load_plugin('provider', provider_def)

        # If the collection has a provider of type feature
        if c_type == "feature":
            # Query using the provider logic and clip = True!
            res = p.query(offset=0,
                          limit=self.processor_def['server']['limit'],
                          resulttype='results', bbox=None,
                          bbox_crs=None, geom_wkt=geom_wkt, geom_crs=geom_crs,
                          datetime_=None, properties=[],
                          sortby=[],
                          select_properties=[],
                          skip_geometry=False,
                          q=None, language='en', filterq=None,
                          clip=1)

        elif c_type == "coverage":
            # Query using the provider logic
            query_args = {
                'geom': geom_wkt,
                'geom_crs': geom_crs,
                'format_': 'native'
            }
            res = p.query(**query_args)

        else:
            res = None
            pass  # Skip, unsupported

        # Return the query result
        return res

    def on_query_validate_inputs(self, data: dict):
        """
        Override this method to perform input validations.

        :param data: the input parameters, as-received, for the process

        :returns: returns True when inputs were all valid. Otherwise raises
        an exception.
        """

        if "collections" in data and data['collections']:
            # Store the collections
            self.colls = data['collections']

            # Check if each collection exists
            for c in self.colls:
                if c not in self.processor_def['collections']:
                    # Error
                    err = CollectionsNotFoundException(c)
                    LOGGER.warning(err)
                    raise err

        else:
            # Error
            err = CollectionsUndefinedException()
            LOGGER.warning(err)
            raise err

        if "geom" in data and data['geom']:
            # Store the input geometry
            self.geom_wkt = data['geom']

        else:
            # Error
            err = ClippingAreaUndefinedException()
            LOGGER.warning(err)
            raise err

        if "geom_crs" in data and data["geom_crs"]:
            # Store the crs
            self.geom_crs = data["geom_crs"]

        else:
            # Error
            err = ClippingAreaCrsUndefinedException()
            LOGGER.warning(err)
            raise err

        # All good
        return True

    def on_query_validate_execution(self, data: dict):
        """
        Override this method to perform pre-execution validations

        :param data: the input parameters, as-received, for the process

        :returns: returns True when execution is good to go.
        """

        # All good
        return True

    def on_query_finalize(self, data: dict, query_res: dict):
        """
        Override this method to do further things with the extracted results
        of each collection.

        :param data: the input parameters, as-received, for the process
        :param query_res: the extraction results of each collection
        """
        pass

    def on_query_results(self, query_res: dict):
        """
        Override this method to return something else than the results
        as json.

        :param query_res: the extraction results of each collection

        :returns: returns the results as json
        """

        # Return the query results
        return 'application/json', query_res

    def on_exception(self, exception: Exception):
        """
        Override this method to do further things when an exception happened.

        :param exception: the exception which happened
        """

        pass

    @staticmethod
    def _get_collection_type_from_providers(providers: list):
        """
        Utility function to get a collection type from the providers list.
        """

        # For each provider
        for p in providers:
            if p['type'] == "feature":
                return "feature"
            elif p['type'] == "coverage":
                return "coverage"
        return None

    @staticmethod
    def _get_collection_mimetype_image_from_providers(providers: list):
        """
        Utility function to get a coverage mimetype from the providers list.
        """

        # For each provider
        for p in providers:
            if p['type'] == "coverage":
                if 'format' in p and 'mimetype' in p['format']:
                    return p['format']['mimetype']
        return None

    def __repr__(self):
        return f'<ExtractProcessor> {self.name}'


class CollectionsUndefinedException(ProviderPreconditionFailed):
    """Exception raised when no collections are defined"""
    def __init__(self):
        super().__init__("Input parameter 'collections' is undefined")


class CollectionsNotFoundException(ProviderPreconditionFailed):
    """Exception raised when a collection wasn't found"""
    def __init__(self, coll_name: str):
        self.coll_name = coll_name
        super().__init__(f"Collection \"{coll_name}\" not found")


class ClippingAreaUndefinedException(ProviderPreconditionFailed):
    """Exception raised when no clipping area is defined"""
    def __init__(self):
        super().__init__("Input parameter 'geom' is undefined")


class ClippingAreaCrsUndefinedException(ProviderPreconditionFailed):
    """Exception raised when no clipping area is defined"""
    def __init__(self):
        super().__init__("Input parameter 'geom_crs' is undefined")
