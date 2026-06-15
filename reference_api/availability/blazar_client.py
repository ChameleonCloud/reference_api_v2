"""Blazar API adapter for reading availability data."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import openstack.config
from blazarclient.client import Client as _BlazarClient  # type: ignore[import-untyped]

from reference_api.availability.models import Interval

LOG = logging.getLogger(__name__)

_DT_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


class BlazarClient:  # pylint: disable=too-few-public-methods
    def __init__(self, cloud_name: str) -> None:
        cloud = openstack.config.OpenStackConfig().get_one(cloud=cloud_name)
        self._client = _BlazarClient(
            "1", service_type="reservation", session=cloud.get_session()
        )

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
