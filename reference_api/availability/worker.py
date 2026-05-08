"""Background worker that polls Blazar and keeps the availability cache current."""
import asyncio
import logging

from reference_api.availability.blazar_client import BlazarClient
from reference_api.availability.cache import AvailabilityCache

LOG = logging.getLogger(__name__)

_DEFAULT_SITE_TIMEOUT = 120.0
_DEFAULT_ERROR_BACKOFF = 60.0


async def run_sync_loop(
    cache: AvailabilityCache,
    site_configs: dict[str, str],  # {site_id: cloud_name}
    poll_interval: float,
    site_timeout: float = _DEFAULT_SITE_TIMEOUT,
    error_backoff: float = _DEFAULT_ERROR_BACKOFF,
) -> None:
    """Poll Blazar at each configured site on a fixed interval."""
    while True:
        try:
            for site_id, cloud_name in site_configs.items():
                try:
                    await _sync_site(cache, site_id, cloud_name, site_timeout)
                except Exception:  # pylint: disable=broad-exception-caught
                    LOG.exception("Availability sync failed for site %s", site_id)
            await asyncio.sleep(poll_interval)
        except Exception:  # pylint: disable=broad-exception-caught
            LOG.exception("Unexpected error in availability sync loop, backing off")
            await asyncio.sleep(error_backoff)


async def _sync_site(
    cache: AvailabilityCache,
    site_id: str,
    cloud_name: str,
    site_timeout: float,
) -> None:
    loop = asyncio.get_running_loop()

    def _fetch():
        client = BlazarClient(cloud_name)
        return client.list_host_allocations()

    nodes, known_uuids = await asyncio.wait_for(
        loop.run_in_executor(None, _fetch),
        timeout=site_timeout,
    )
    await cache.update_site(site_id, nodes, known_uuids)
    LOG.info("Synced availability for site %s: %d nodes", site_id, len(known_uuids))
