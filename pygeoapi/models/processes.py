import datetime as dt
from typing import Literal, List, Optional

import pydantic

from pygeoapi.util import JobStatus


class Link(pydantic.BaseModel):
    href: str
    type_: Optional[str] = pydantic.Field(None, alias="type")
    rel: Optional[str] = None
    title: Optional[str] = None
    href_lang: Optional[str] = pydantic.Field(None, alias="hreflang")


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


class JobList(pydantic.BaseModel):
    jobs: List[JobStatusInfoRead]
    links: List[Link]
