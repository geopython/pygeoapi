from typing import List, Optional

from specklepy.objects.base import Base


class GisFeature(
    Base, speckle_type="Objects.GIS.GisFeature", detachable={"displayValue"}
):
    """GIS Feature"""

    geometry: Optional[List[Base]] = None
    attributes: Base
    displayValue: Optional[List[Base]] = None
