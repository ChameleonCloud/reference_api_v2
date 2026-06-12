from datetime import datetime
from typing import NamedTuple, Optional

from pydantic import BaseModel, ConfigDict


class Interval(NamedTuple):
    start: datetime
    end: datetime


class Reservation(BaseModel):
    start: datetime
    end: datetime


class NodeAvailabilityResponse(BaseModel):
    node_id: str
    cluster_id: str
    site_id: str
    last_updated: datetime
    maintenance: bool = False
    reservations: list[Reservation]


class SearchNodeItem(BaseModel):
    uid: Optional[str] = None
    node_type: Optional[str] = None
    site_id: str
    cluster_id: str
    availability: str  # "available" | "reserved" | "unknown"
    availability_until: Optional[datetime] = None
    model_config = ConfigDict(extra="allow")


class NodeSearchResponse(BaseModel):
    total: int
    offset: int
    items: list[SearchNodeItem]
