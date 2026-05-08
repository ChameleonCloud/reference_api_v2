"""Blazar API adapter for reading availability data."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import openstack.config
from blazarclient.client import Client as _BlazarClient  # type: ignore[import-untyped]

from reference_api.availability.models import Interval

LOG = logging.getLogger(__name__)

_DT_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
_ACTIVE_STATUSES = frozenset({"PENDING", "ACTIVE"})


class BlazarClient:  # pylint: disable=too-few-public-methods
    def __init__(self, cloud_name: str) -> None:
        cloud = openstack.config.OpenStackConfig().get_one(cloud=cloud_name)
        self._client = _BlazarClient(
            "1", service_type="reservation", session=cloud.get_session()
        )

    def _active_leases(self) -> list[dict]:
        return [lease for lease in self._client.lease.list() if lease["status"] in _ACTIVE_STATUSES]

    def list_host_allocations(self) -> tuple[dict[str, list[Interval]], frozenset[str]]:
        """Return ({uuid: [Interval, ...]}, known_uuids) for PENDING/ACTIVE leases."""
        uuid_by_blazar_id = {
            h["id"]: h["hypervisor_hostname"]
            for h in self._client.host.list()
            if h.get("hypervisor_hostname")
        }
        known_uuids = frozenset(uuid_by_blazar_id.values())

        windows: dict[str, Interval] = {}
        for lease in self._active_leases():
            start = _parse_dt(lease.get("start_date"))
            end = _parse_dt(lease.get("end_date"))
            if start and end:
                windows[lease["id"]] = Interval(start, end)

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
        return result, known_uuids


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
