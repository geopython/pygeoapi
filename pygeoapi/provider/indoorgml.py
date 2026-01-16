import logging
import json
from pygeoapi.provider.base import BaseProvider, ProviderItemNotFoundError

LOGGER = logging.getLogger(__name__)

class IndoorGMLProvider(BaseProvider):
    """STEMLab IndoorGML/IndoorJSON Provider"""

    def __init__(self, provider_def):
        """Initialize the provider with the config and data source"""
        super().__init__(provider_def)
        # This is the path to your .json or .gml file defined in the config
        self.data_path = self.data 
        self.id_field = provider_def.get('id_field', 'id')

    def query(self, offset=0, limit=10, resulttype='results', **kwargs):
        features = []
        with open(self.data_path, 'r') as f:
            data = json.load(f)
        
        # IndoorJSON Hierarchy Navigation
        for layer in data.get('layers', []):
            # 1. Extract Physical Rooms (CellSpaces)
            primal = layer.get('primalSpace', {})
            for cell in primal.get('cellSpaceMember', []):
                features.append({
                    'type': 'Feature',
                    'id': cell.get('id'),
                    'geometry': cell.get('cellSpaceGeom', {}).get('geometry2D'),
                    'properties': {
                        'type': 'CellSpace',
                        'level': cell.get('level'),
                        'duality': cell.get('duality')
                    }
                })
            
            # 2. Extract Logical Nodes (for navigation research)
            dual = layer.get('dualSpace', {})
            for node in dual.get('nodeMember', []):
                features.append({
                    'type': 'Feature',
                    'id': node.get('id'),
                    'geometry': node.get('geometry'),
                    'properties': {
                        'type': 'Node',
                        'duality': node.get('duality')
                    }
                })

        return {
            'type': 'FeatureCollection',
            'features': features[offset:offset + limit]
        }

    def get(self, identifier, **kwargs):
        """Returns a single Indoor feature (e.g., a specific Room) by its ID"""
        # TODO: Implement lookup logic for a single ID
        pass

    def __repr__(self):
        return f'<IndoorGMLProvider> {self.data_path}'