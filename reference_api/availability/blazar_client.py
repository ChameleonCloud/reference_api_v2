"""Blazar API adapter for reading availability data."""
from __future__ import annotations

import logging
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

    def list_host_allocations(
        self,
    ) -> tuple[dict[str, list[Interval]], frozenset[str], frozenset[str]]:
        """Return (reservations, known_uuids, unavailable_uuids).

        unavailable_uuids contains nodes that are disabled or non-reservable.
        """
        LOG.debug("Fetching hosts from Blazar")
        all_hosts = self._client.host.list()
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

        LOG.debug("Fetching leases from Blazar")
        windows: dict[str, Interval] = {}
        for lease in self._client.lease.list():
            start = _parse_dt(lease.get("start_date"))
            end = _parse_dt(lease.get("end_date"))
            if start and end:
                windows[lease["id"]] = Interval(start, end)
        LOG.debug("Found %d active lease windows", len(windows))

        LOG.debug("Fetching host allocations from Blazar")
        result: dict[str, list[Interval]] = {}
        for alloc in self._client.allocation.list("os-hosts"):
            node_uuid = uuid_by_blazar_id.get(alloc["resource_id"])
            if not node_uuid:
                continue
            result[node_uuid] = [
                windows[r["lease_id"]]
                for r in alloc.get("reservations", [])
                if r.get("lease_id") in windows
            ]
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
