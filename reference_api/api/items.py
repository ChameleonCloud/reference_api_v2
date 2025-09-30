"""Item models for API responses
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class Link(BaseModel):
    rel: str
    href: str


class VersionItem(BaseModel):
    id: str
    message: Optional[str] = None
    date: Optional[str] = None


class BaseItem(BaseModel):
    uid: Optional[str] = None


class SiteItem(BaseItem):
    name: Optional[str] = None
    description: Optional[str] = None
    email_contact: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location: Optional[str] = None
    security_contact: Optional[str] = None
    site_class: Optional[str] = None
    sys_admin_contact: Optional[str] = None
    user_support_contact: Optional[str] = None
    web: Optional[str] = None
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


class ClusterItem(BaseItem):
    created_at: Optional[str] = None
    queues: List[str] = Field(default_factory=list)
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")


class NodeItem(BaseModel):
    uid: Optional[str] = None
    node_name: Optional[str] = None
    node_type: Optional[str] = None
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)
    model_config = ConfigDict(extra="allow")
