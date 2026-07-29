"""Blazar API adapter for reading availability data."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import openstack
import openstack.config
import openstack.connection
from blazarclient.client import Client as _BlazarClient  # type: ignore[import-untyped]

from reference_api.availability.models import Interval

LOG = logging.getLogger(__name__)

_DT_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
_FLAVOR_DATE_FORMAT = "%Y-%m-%d %H:%M"

_flavor_id_cache: dict[tuple[str, str], str] = {}


class BlazarClient:  # pylint: disable=too-few-public-methods
    def __init__(self, cloud_name: str) -> None:
        self._cloud_name = cloud_name
        cloud = openstack.config.OpenStackConfig().get_one(cloud=cloud_name)
        session = cloud.get_session()
        self._client = _BlazarClient(
            "1", service_type="reservation", session=session
        )
        self._conn = openstack.connection.Connection(config=cloud)

    def warmup_flavor(self, flavor_id: str) -> None:
        """Pre-populate the flavor ID cache."""
        self._resolve_flavor_id(flavor_id)

    def _resolve_flavor_id(self, flavor_id: str) -> str:
        cache_key = (self._cloud_name, flavor_id)
        if cache_key in _flavor_id_cache:
            return _flavor_id_cache[cache_key]
        LOG.debug("Nova: resolving flavor %r on %s", flavor_id, self._cloud_name)
        flavor = self._conn.compute.find_flavor(flavor_id)
        if flavor is None:
            raise LookupError(f"Flavor not found: {flavor_id!r}")
        LOG.debug("Nova: resolved %r -> %s", flavor_id, flavor.id)
        _flavor_id_cache[cache_key] = flavor.id
        return flavor.id

    def list_host_allocations(  # pylint: disable=too-many-locals
        self,
    ) -> tuple[dict[str, list[Interval]], frozenset[str], frozenset[str]]:
        """Return (reservations, known_uuids, unavailable_uuids).

        unavailable_uuids contains nodes that are disabled or non-reservable.
        """
        LOG.debug("Fetching hosts and allocations from Blazar")
        with ThreadPoolExecutor(max_workers=2) as executor:
            hosts_future = executor.submit(self._client.host.list)
            allocations_future = executor.submit(self._client.allocation.list, "os-hosts")

        all_hosts = hosts_future.result()
        allocations = allocations_future.result()

        uuid_by_blazar_id = {
            h["id"]: h["hypervisor_hostname"]
            for h in all_hosts
            if h.get("hypervisor_hostname")
        }
        known_uuids = frozenset(uuid_by_blazar_id.values())
        unavailable_uuids = frozenset(
            h["hypervisor_hostname"]
            for h in all_hosts
            if h.get("hypervisor_hostname")
            and not (h.get("reservable", True) and not h.get("disabled", False))
        )
        LOG.debug("Found %d hosts (%d unavailable)", len(known_uuids), len(unavailable_uuids))

        result: dict[str, list[Interval]] = {}
        for alloc in allocations:
            node_uuid = uuid_by_blazar_id.get(alloc["resource_id"])
            if not node_uuid:
                continue
            intervals = []
            for r in alloc.get("reservations", []):
                start = _parse_dt(r.get("start_date"))
                end = _parse_dt(r.get("end_date"))
                if start and end:
                    intervals.append(Interval(start, end))
            result[node_uuid] = intervals
        return result, known_uuids, unavailable_uuids

    def get_flavor_availability(
        self, flavor_id: str, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        if not hasattr(self._client, "flavor_instance"):
            raise RuntimeError("blazarclient does not have flavor_instance support")
        nova_id = self._resolve_flavor_id(flavor_id)
        start_str = start_date.strftime(_FLAVOR_DATE_FORMAT)
        end_str = end_date.strftime(_FLAVOR_DATE_FORMAT)
        LOG.debug(
            "Blazar: fetching flavor availability for %s (%s to %s)",
            nova_id, start_str, end_str,
        )
        result = self._client.flavor_instance.get_availability(
            flavor_id=nova_id,
            start_date=start_str,
            end_date=end_str,
        )
        LOG.debug(
            "Blazar: received %d flavor_instance entries",
            len(result.get("flavor_instances", [])),
        )
        entries = result.get("flavor_instances", [])
        for entry in entries:
            for seg in entry.get("availability", []):
                seg["start"] = datetime.strptime(seg["start"], _FLAVOR_DATE_FORMAT)
                seg["end"] = datetime.strptime(seg["end"], _FLAVOR_DATE_FORMAT)
        return entries


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (_DT_FORMAT, "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    LOG.warning("Unexpected Blazar datetime format: %r", value)
    return None
