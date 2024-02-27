from dataclasses import dataclass
from typing import Dict, List, Iterable


@dataclass
class ConformanceClasses:
    name: str
    classes: List[str]


def get_conformance_classes(ogc_specs: List[
        ConformanceClasses]) -> Iterable[Dict[str, List[str]]]:
    """Get an iterable of OGC API conformance classes"""
    return ({spec.name: spec.classes} for spec in ogc_specs)
