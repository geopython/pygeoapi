import hashlib
import re
import warnings
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from warnings import warn

import ujson

# import for serialization
from specklepy.logging.exceptions import SpeckleException, SpeckleWarning
from specklepy.objects.base import Base, DataChunk
from specklepy.transports.abstract_transport import AbstractTransport

PRIMITIVES = (int, float, str, bool)


def hash_obj(obj: Any) -> str:
    return hashlib.sha256(ujson.dumps(obj).encode()).hexdigest()[:32]


def safe_json_loads(obj: str, obj_id=None) -> Any:
    try:
        return ujson.loads(obj)
    except ValueError as err:
        import json

        warn(
            f"Failed to deserialise object (id: {obj_id}). This is likely a ujson big"
            f" int error - falling back to json. \nError: {err}",
            SpeckleWarning,
        )
        try:
            return ujson.loads(obj[:-2])
        except:
            return json.loads(obj)


class BaseObjectSerializer:
    read_transport: AbstractTransport
    write_transports: List[AbstractTransport]
    detach_lineage: List[bool]  # tracks depth and whether or not to detach
    lineage: List[str]  # keeps track of hash chain through the object tree
    family_tree: Dict[str, Dict[str, int]]
    closure_table: Dict[str, Dict[str, int]]
    deserialized: Dict[
        str, Base
    ]  # holds deserialized objects so objects with same id return the same instance

    def __init__(
        self,
        write_transports: Optional[List[AbstractTransport]] = None,
        read_transport: Optional[AbstractTransport] = None,
    ) -> None:
        self.write_transports = write_transports or []
        self.read_transport = read_transport
        self.detach_lineage = []
        self.lineage = []
        self.family_tree = {}
        self.closure_table = {}
        self.deserialized = {}

    def write_json(self, base: Base):
        """Serializes a given base object into a json string
        Arguments:
            base {Base} -- the base object to be decomposed and serialized

        Returns:
            (str, str) -- a tuple containing the object id of the base object and
            the serialized object string
        """

        obj_id, obj = self.traverse_base(base)

        return obj_id, ujson.dumps(obj)

    def traverse_base(self, base: Base) -> Tuple[str, Dict[str, Any]]:
        """Decomposes the given base object and builds a serializable dictionary

        Arguments:
            base {Base} -- the base object to be decomposed and serialized

        Returns:
            (str, dict) -- a tuple containing the object id of the base object and
            the constructed serializable dictionary
        """
        self.__reset_writer()

        if self.write_transports:
            for wt in self.write_transports:
                wt.begin_write()

        obj_id, obj = self._traverse_base(base)

        if self.write_transports:
            for wt in self.write_transports:
                wt.end_write()

        return obj_id, obj

    def _traverse_base(self, base: Base) -> Tuple[str, Dict]:
        if not self.detach_lineage:
            self.detach_lineage = [True]

        self.lineage.append(uuid4().hex)
        object_builder = {"id": "", "speckle_type": "Base", "totalChildrenCount": 0}
        object_builder.update(speckle_type=base.speckle_type)
        obj, props = base, base.get_serializable_attributes()

        while props:
            prop = props.pop(0)
            value = getattr(obj, prop, None)
            chunkable = False
            detach = False

            # skip props marked to be ignored with "__" or "_"
            if prop.startswith(("__", "_")):
                continue

            # don't prepopulate id as this will mess up hashing
            if prop == "id":
                continue

            # only bother with chunking and detaching if there is a write transport
            if self.write_transports:
                dynamic_chunk_match = prop.startswith("@") and re.match(
                    r"^@\((\d*)\)", prop
                )
                if dynamic_chunk_match:
                    chunk_size = dynamic_chunk_match.groups()[0]
                    base._chunkable[prop] = (
                        int(chunk_size) if chunk_size else base._chunk_size_default
                    )

                chunkable = prop in base._chunkable
                detach = bool(
                    prop.startswith("@") or prop in base._detachable or chunkable
                )

            # 1. handle None and primitives (ints, floats, strings, and bools)
            if value is None or isinstance(value, PRIMITIVES):
                object_builder[prop] = value
                continue

            # NOTE: for dynamic props, this won't be re-serialised as an enum but as an int
            if isinstance(value, Enum):
                object_builder[prop] = value.value
                continue

            # 2. handle Base objects
            elif isinstance(value, Base):
                child_obj = self.traverse_value(value, detach=detach)
                if detach and self.write_transports:
                    ref_id = child_obj["id"]
                    object_builder[prop] = self.detach_helper(ref_id=ref_id)
                else:
                    object_builder[prop] = child_obj

            # 3. handle chunkable props
            elif chunkable and self.write_transports:
                chunks = []
                max_size = base._chunkable[prop]
                chunk = DataChunk()
                for count, item in enumerate(value):
                    if count and count % max_size == 0:
                        chunks.append(chunk)
                        chunk = DataChunk()
                    chunk.data.append(item)
                chunks.append(chunk)

                chunk_refs = []
                for c in chunks:
                    self.detach_lineage.append(detach)
                    ref_id, _ = self._traverse_base(c)
                    ref_obj = self.detach_helper(ref_id=ref_id)
                    chunk_refs.append(ref_obj)
                object_builder[prop] = chunk_refs

            # 4. handle all other cases
            else:
                child_obj = self.traverse_value(value, detach)
                object_builder[prop] = child_obj

        closure = {}
        # add closures & children count to the object
        detached = self.detach_lineage.pop()
        if self.lineage[-1] in self.family_tree:
            closure = {
                ref: depth - len(self.detach_lineage)
                for ref, depth in self.family_tree[self.lineage[-1]].items()
            }
        object_builder["totalChildrenCount"] = len(closure)

        obj_id = hash_obj(object_builder)

        object_builder["id"] = obj_id
        if closure:
            object_builder["__closure"] = self.closure_table[obj_id] = closure

        # write detached or root objects to transports
        if detached and self.write_transports:
            for t in self.write_transports:
                t.save_object(id=obj_id, serialized_object=ujson.dumps(object_builder))

        del self.lineage[-1]

        return obj_id, object_builder

    def traverse_value(self, obj: Any, detach: bool = False) -> Any:
        """Decomposes a given object and constructs a serializable object or dictionary

        Arguments:
            obj {Any} -- the value to decompose

        Returns:
            Any -- a serializable version of the given object
        """
        if obj is None:
            return None
        if isinstance(obj, PRIMITIVES):
            return obj

        # NOTE: for dynamic props, this won't be re-serialised as an enum but as an int
        if isinstance(obj, Enum):
            return obj.value

        elif isinstance(obj, (list, tuple, set)):
            if not detach:
                return [self.traverse_value(o) for o in obj]

            detached_list = []
            for o in obj:
                if isinstance(o, Base):
                    self.detach_lineage.append(detach)
                    ref_id, _ = self._traverse_base(o)
                    detached_list.append(self.detach_helper(ref_id=ref_id))
                else:
                    detached_list.append(self.traverse_value(o, detach))
            return detached_list

        elif isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, PRIMITIVES) or v is None:
                    continue
                else:
                    obj[k] = self.traverse_value(v)
            return obj

        elif isinstance(obj, Base):
            self.detach_lineage.append(detach)
            _, base_obj = self._traverse_base(obj)
            return base_obj

        else:
            try:
                return obj.dict()
            except Exception:
                warn(
                    f"Failed to handle {type(obj)} in"
                    " `BaseObjectSerializer.traverse_value`",
                    SpeckleWarning,
                )

                return str(obj)

    def detach_helper(self, ref_id: str) -> Dict[str, str]:
        """
        Helper to keep track of detached objects and their depth in the family tree
        and create reference objects to place in the parent object

        Arguments:
            ref_id {str} -- the id of the fully traversed object

        Returns:
            dict -- a reference object to be inserted into the given object's parent
        """

        for parent in self.lineage:
            if parent not in self.family_tree:
                self.family_tree[parent] = {}
            if ref_id not in self.family_tree[parent] or self.family_tree[parent][
                ref_id
            ] > len(self.detach_lineage):
                self.family_tree[parent][ref_id] = len(self.detach_lineage)

        return {
            "referencedId": ref_id,
            "speckle_type": "reference",
        }

    def __reset_writer(self) -> None:
        """
        Reinitializes the lineage, and other variables that get used during the json
        writing process
        """
        self.detach_lineage = [True]
        self.lineage = []
        self.family_tree = {}
        self.closure_table = {}

    def read_json(self, obj_string: str) -> Base:
        """Recomposes a Base object from the string representation of the object

        Arguments:
            obj_string {str} -- the string representation of the object

        Returns:
            Base -- the base object with all it's children attached
        """
        if not obj_string:
            return None

        self.deserialized = {}
        obj = safe_json_loads(obj_string)
        return self.recompose_base(obj=obj)

    def recompose_base(self, obj: dict) -> Base:
        """Steps through a base object dictionary and recomposes the base object

        Arguments:
            obj {dict} -- the dictionary representation of the object

        Returns:
            Base -- the base object with all its children attached
        """
        # make sure an obj was passed and create dict if string was somehow passed
        if not obj:
            return

        if isinstance(obj, str):
            obj = safe_json_loads(obj)

        if "id" in obj and obj["id"] in self.deserialized:
            return self.deserialized[obj["id"]]

        if "speckle_type" in obj and obj["speckle_type"] == "reference":
            obj = self.get_child(obj=obj)

        speckle_type = obj.get("speckle_type")
        # if speckle type is not in the object definition, it is treated as a dict
        if not speckle_type:
            return obj

        # get the registered type from base register.
        object_type = Base.get_registered_type(speckle_type)

        # initialise the base object using `speckle_type` fall back to base if needed
        base = object_type() if object_type else Base.of_type(speckle_type=speckle_type)
        # get total children count
        if "__closure" in obj:
            if not self.read_transport:
                raise SpeckleException(
                    message="Cannot resolve reference - no read transport is defined"
                )
            closure = obj.pop("__closure")
            base.totalChildrenCount = len(closure)

        for prop, value in obj.items():
            # 1. handle primitives (ints, floats, strings, and bools) or None
            if isinstance(value, PRIMITIVES) or value is None:
                base.__setattr__(prop, value)
                continue

            # 2. handle referenced child objects
            elif "referencedId" in value:
                ref_id = value["referencedId"]
                ref_obj_str = self.read_transport.get_object(id=ref_id)
                if ref_obj_str:
                    ref_obj = safe_json_loads(ref_obj_str, ref_id)
                    base.__setattr__(prop, self.recompose_base(obj=ref_obj))
                else:
                    warnings.warn(
                        f"Could not find the referenced child object of id `{ref_id}`"
                        f" in the given read transport: {self.read_transport.name}",
                        SpeckleWarning,
                    )
                    base.__setattr__(prop, self.handle_value(value))

            # 3. handle all other cases (base objects, lists, and dicts)
            else:
                base.__setattr__(prop, self.handle_value(value))

        if "id" in obj:
            self.deserialized[obj["id"]] = base

        return base

    def handle_value(self, obj: Any):
        """Helper for recomposing a base object by handling the dictionary
        representation's values

        Arguments:
            obj {Any} -- a value from the base object dictionary

        Returns:
            Any -- the handled value (primitive, list, dictionary, or Base)
        """
        if not obj:
            return obj

        if isinstance(obj, PRIMITIVES):
            return obj

        # lists (regular and chunked)
        if isinstance(obj, list):
            obj_list = [self.handle_value(o) for o in obj]
            if (
                hasattr(obj_list[0], "speckle_type")
                and "DataChunk" in obj_list[0].speckle_type
            ):
                # handle chunked lists
                data = []
                for o in obj_list:
                    data.extend(o.data)
                return data
            return obj_list

        # bases
        if isinstance(obj, dict) and "speckle_type" in obj:
            return self.recompose_base(obj=obj)

        # dictionaries
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, PRIMITIVES):
                    continue
                else:
                    obj[k] = self.handle_value(v)
            return obj

    def get_child(self, obj: Dict):
        ref_id = obj["referencedId"]
        ref_obj_str = self.read_transport.get_object(id=ref_id)
        if not ref_obj_str:
            warnings.warn(
                f"Could not find the referenced child object of id `{ref_id}` in the"
                f" given read transport: {self.read_transport.name}",
                SpeckleWarning,
            )
            return obj

        return safe_json_loads(ref_obj_str, ref_id)
