import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from reference_api.availability.models import Interval


@dataclass
class _SiteData:
    last_synced: datetime
    nodes: dict[str, list[Interval]] = field(default_factory=dict)
    known_nodes: frozenset[str] = field(default_factory=frozenset)
    unavailable_nodes: frozenset[str] = field(default_factory=frozenset)


class AvailabilityCache:
    """Async-safe in-memory store for Blazar availability data, keyed by site_id."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._data: dict[str, _SiteData] = {}

    async def update_site(
        self,
        site_id: str,
        nodes: dict[str, list[Interval]],
        known_nodes: frozenset[str],
        unavailable_nodes: frozenset[str],
    ) -> None:
        """Replace all availability data for a site."""
        async with self._lock:
            self._data[site_id] = _SiteData(
                last_synced=datetime.now(timezone.utc),
                nodes=nodes,
                known_nodes=known_nodes,
                unavailable_nodes=unavailable_nodes,
            )

    async def get_node(
        self, site_id: str, node_uuid: str
    ) -> tuple[datetime, list[Interval] | None, bool] | None:
        # None              = site never synced
        # (dt, None, False) = site synced, node not registered in Blazar
        # (dt, [], True)    = site synced, node in maintenance/disabled
        # (dt, [], False)   = site synced, node free
        # (dt, [...], False)= site synced, node has reservations
        async with self._lock:
            site = self._data.get(site_id)
            if site is None:
                return None
            if node_uuid not in site.known_nodes:
                return site.last_synced, None, False
            maintenance = node_uuid in site.unavailable_nodes
            return site.last_synced, list(site.nodes.get(node_uuid, [])), maintenance

    async def get_site_nodes(
        self, site_id: str
    ) -> tuple[dict[str, list[Interval]], frozenset[str]] | None:
        async with self._lock:
            site = self._data.get(site_id)
            if site is None:
                return None
            return dict(site.nodes), frozenset(site.unavailable_nodes)

    async def get_site_last_synced(
        self, site_id: str
    ) -> tuple[datetime, int] | None:
        async with self._lock:
            site = self._data.get(site_id)
            if site is None:
                return None
            return site.last_synced, len(site.nodes)
