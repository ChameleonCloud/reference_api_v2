"""Collection models for API responses
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class SiteCollection(BaseModel):
    total: int
    offset: int
    items: List[Any]
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)


class ClusterCollection(BaseModel):
    total: int
    offset: int
    items: List[Any]
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)


class NodeCollection(BaseModel):
    total: int
    offset: int
    items: List[Any]
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)


class VersionCollection(BaseModel):
    total: int
    offset: int
    items: List[Any]
    version: Optional[str] = None
    links: List[Any] = Field(default_factory=list)
