import datetime as dt
import enum
from typing import Any, Dict, Literal, List, Optional, Union

import pydantic


class JobStatus(enum.Enum):
    """
    Enum for the job status options specified in the WPS 2.0 specification
    """

    #  From the specification
    accepted = 'accepted'
    running = 'running'
    successful = 'successful'
    failed = 'failed'
    dismissed = 'dismissed'


class ProcessOutputTransmissionMode(enum.Enum):
    VALUE = "value"
    REFERENCE = "reference"


class ProcessResponseType(enum.Enum):
    document = "document"
    raw = "raw"


class ProcessJobControlOption(enum.Enum):
    SYNC_EXECUTE = "sync-execute"
    ASYNC_EXECUTE = "async-execute"
    DISMISS = "dismiss"


class ProcessIOType(enum.Enum):
    ARRAY = "array"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    OBJECT = "object"
    STRING = "string"


class ProcessIOFormat(enum.Enum):
    # this is built from:
    # - the jsonschema spec at: https://json-schema.org/draft/2020-12/json-schema-validation.html#name-defined-formats
    # - the OAPI - Processes spec (table 13) at: https://docs.ogc.org/is/18-062r2/18-062r2.html#ogc_process_description
    DATE_TIME = "date-time"
    DATE = "date"
    TIME = "time"
    DURATION = "duration"
    EMAIL = "email"
    HOSTNAME = "hostname"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    URI = "uri"
    URI_REFERENCE = "uri-reference"
    # left out `iri` and `iri-reference` as valid URIs are also valid IRIs
    UUID = "uuid"
    URI_TEMPLATE = "uri-template"
    JSON_POINTER = "json-pointer"
    RELATIVE_JSON_POINTER = "relative-json-pointer"
    REGEX = "regex"
    # the below `binary` entry does not seem to be defined in the jsonschema spec
    # nor in OAPI - Processes - but it is mentioned in OAPI - Processes spec as an example
    BINARY = "binary"
    GEOJSON_FEATURE_COLLECTION_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-feature-collection"
    GEOJSON_FEATURE_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-feature"
    GEOJSON_GEOMETRY_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/geojson-geometry"
    OGC_BBOX_URI = "http://www.opengis.net/def/format/ogcapi-processes/0/ogc-bbox"
    GEOJSON_FEATURE_COLLECTION_SHORT_CODE = "geojson-feature-collection"
    GEOJSON_FEATURE_SHORT_CODE = "geojson-feature"
    GEOJSON_GEOMETRY_SHORT_CODE = "geojson-geometry"
    OGC_BBOX_SHORT_CODE = "ogc-bbox"


class Link(pydantic.BaseModel):
    href: str
    type_: Optional[str] = pydantic.Field(None, alias="type")
    rel: Optional[str] = None
    title: Optional[str] = None
    href_lang: Optional[str] = pydantic.Field(None, alias="hreflang")


# this is a 'pydantification' of the schema.yml fragment, as shown
# on the OAPI - Processes spec
class ProcessIOSchema(pydantic.BaseModel):
    title: Optional[str] = None
    multiple_of: Optional[float] = pydantic.Field(None, alias="multipleOf")
    maximum: Optional[float] = None
    exclusive_maximum: Optional[bool] = pydantic.Field(
        False, alias="exclusiveMaximum")
    minimum: Optional[float] = None
    exclusive_minimum: Optional[bool] = pydantic.Field(
        False, alias="exclusiveMinimum")
    max_length: int = pydantic.Field(None, ge=0, alias="maxLength")
    min_length: int = pydantic.Field(0, ge=0, alias="minLength")
    pattern: Optional[str] = None
    max_items: Optional[int] = pydantic.Field(None, ge=0, alias="maxItems")
    min_items: Optional[int] = pydantic.Field(0, ge=0, alias="minItems")
    unique_items: Optional[bool] = pydantic.Field(False, alias="uniqueItems")
    max_properties: Optional[int] = pydantic.Field(
        None, ge=0, alias="maxProperties")
    min_properties: Optional[int] = pydantic.Field(
        0, ge=0, alias="minProperties")
    required: Optional[
        pydantic.conlist(str, min_items=1, unique_items=True)] = None
    enum: Optional[
        pydantic.conlist(Any, min_items=1, unique_items=False)] = None
    type_: Optional[ProcessIOType] = pydantic.Field(None, alias="type")
    not_: Optional["ProcessIOSchema"] = pydantic.Field(None, alias="not")
    allOf: Optional[List["ProcessIOSchema"]] = None
    oneOf: Optional[List["ProcessIOSchema"]] = None
    anyOf: Optional[List["ProcessIOSchema"]] = None
    items: Optional[List["ProcessIOSchema"]] = None
    properties: Optional["ProcessIOSchema"] = None
    additional_properties: Optional[
        Union[bool, "ProcessIOSchema"]
    ] = pydantic.Field(True, alias="additionalProperties")
    description: Optional[str] = None
    format_: Optional[ProcessIOFormat] = pydantic.Field(None, alias="format")
    default: Optional[pydantic.Json[dict]] = None
    nullable: Optional[bool] = False
    read_only: Optional[bool] = pydantic.Field(False, alias="readOnly")
    write_only: Optional[bool] = pydantic.Field(False, alias="writeOnly")
    example: Optional[pydantic.Json[dict]] = None
    deprecated: Optional[bool] = False
    content_media_type: Optional[str] = pydantic.Field(
        None, alias="contentMediaType")
    content_encoding: Optional[str] = pydantic.Field(
        None, alias="contentEncoding")
    content_schema: Optional[str] = pydantic.Field(None, alias="contentSchema")

    class Config:
        use_enum_values = True


class ProcessOutput(pydantic.BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    schema_: ProcessIOSchema = pydantic.Field(alias="schema")


class ProcessMetadata(pydantic.BaseModel):
    title: Optional[str] = None
    role: Optional[str] = None
    href: Optional[str] = None


class AdditionalProcessIOParameters(ProcessMetadata):
    name: str
    value: List[Union[str, float, int, List[Dict], Dict]]

    class Config:
        smart_union = True


class ProcessInput(ProcessOutput):
    keywords: Optional[List[str]] = None
    metadata: Optional[List[ProcessMetadata]] = None
    min_occurs: int = pydantic.Field(1, alias="minOccurs")
    max_occurs: Optional[Union[int, Literal["unbounded"]]] = pydantic.Field(
        1, alias="maxOccurs")
    additional_parameters: Optional[AdditionalProcessIOParameters] = None


class ProcessSummary(pydantic.BaseModel):
    version: str
    id: str
    title: Optional[Union[Dict[str, str], str]] = None
    description: Optional[Union[Dict[str, str], str]] = None
    keywords: Optional[List[str]] = None
    job_control_options: Optional[
        List[ProcessJobControlOption]
    ] = pydantic.Field(
        [ProcessJobControlOption.SYNC_EXECUTE], alias="jobControlOptions")
    output_transmission: Optional[
        List[ProcessOutputTransmissionMode]
    ] = pydantic.Field(
        [ProcessOutputTransmissionMode.VALUE], alias="outputTransmission")
    links: Optional[List[Link]] = None


class ProcessDescription(ProcessSummary):
    inputs: Dict[str, ProcessInput]
    outputs: Dict[str, ProcessOutput]
    example: Optional[dict]


class JobStatusInfoBase(pydantic.BaseModel):
    job_id: str = pydantic.Field(..., alias="jobID")
    process_id: Optional[str] = pydantic.Field(None, alias="processID")
    status: JobStatus
    message: Optional[str] = None
    created: Optional[dt.datetime] = None
    started: Optional[dt.datetime] = None
    finished: Optional[dt.datetime] = None
    updated: Optional[dt.datetime] = None
    progress: Optional[int] = pydantic.Field(None, ge=0, le=100)


class JobStatusInfoInternal(JobStatusInfoBase):
    location: Optional[str] = None


class JobStatusInfoRead(JobStatusInfoBase):
    """OAPI - Processes. Schema for a StatusInfo."""
    type: Literal["process"] = "process"
    links: Optional[List[Link]]

    class Config:
        use_enum_values = True


class ExecutionInputBBox(pydantic.BaseModel):
    bbox: List[float] = pydantic.Field(..., min_items=4, max_items=4)
    crs: Optional[str] = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"


class ExecutionInputValueNoObjectArray(pydantic.BaseModel):
    __root__: List[
        Union[
            ExecutionInputBBox,
            int,
            str,
            "ExecutionInputValueNoObjectArray"
        ]
    ]


class ExecutionInputValueNoObject(pydantic.BaseModel):
    """Models the `inputValueNoObject.yml` schema defined in OAPIP."""
    __root__: Union[
        ExecutionInputBBox,
        bool,
        float,
        int,
        ExecutionInputValueNoObjectArray,
        str,
    ]

    class Config:
        smart_union = True


class ExecutionFormat(pydantic.BaseModel):
    """Models the `format.yml` schema defined in OAPIP."""
    media_type: Optional[str] = pydantic.Field(None, alias="mediaType")
    encoding: Optional[str]
    schema_: Optional[Union[str, dict]] = pydantic.Field(
        None, alias="schema")


class ExecutionQualifiedInputValue(pydantic.BaseModel):
    """Models the `qualifiedInputValue.yml` schema defined in OAPIP."""
    value: Union[ExecutionInputValueNoObject, dict]
    format_: Optional[ExecutionFormat] = None


class ExecutionOutput(pydantic.BaseModel):
    """Models the `output.yml` schema defined in OAPIP."""
    format_: Optional[ExecutionFormat] = pydantic.Field(
        None, alias="format")
    transmission_mode: Optional[
        ProcessOutputTransmissionMode
    ] = pydantic.Field(
        ProcessOutputTransmissionMode.VALUE,
        alias="transmissionMode"
    )

    class Config:
        use_enum_values = True


class ExecutionSubscriber(pydantic.BaseModel):
    """Models the `subscriber.yml` schema defined in OAPIP."""
    success_uri: str = pydantic.Field(..., alias="successUri")
    in_progress_uri: Optional[str] = pydantic.Field(
        None, alias="inProgressUri")
    failed_uri: Optional[str] = pydantic.Field(None, alias="failedUri")


class Execution(pydantic.BaseModel):
    """Models the `execute.yml` schema defined in OAPIP."""
    inputs: Optional[
        Dict[
            str,
            Union[
                ExecutionInputValueNoObject,
                ExecutionQualifiedInputValue,
                Link,
                List[
                    Union[
                        ExecutionInputValueNoObject,
                        ExecutionQualifiedInputValue,
                        Link,
                    ]
                ],
            ]
        ]
    ] = None
    outputs: Optional[Dict[str, ExecutionOutput]] = None
    response: Optional[ProcessResponseType] = ProcessResponseType.raw
    subscriber: Optional[ExecutionSubscriber] = None

    class Config:
        use_enum_values = True


class JobList(pydantic.BaseModel):
    jobs: List[JobStatusInfoRead]
    links: List[Link]


class ProcessList(pydantic.BaseModel):
    processes: List[ProcessSummary]
    links: List[Link]
