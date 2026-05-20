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
    """Spawn an independent sync task per site and run them concurrently."""
    await asyncio.gather(*(
        _site_loop(cache, site_id, cloud_name, poll_interval, site_timeout, error_backoff)
        for site_id, cloud_name in site_configs.items()
    ))


async def _site_loop(
    cache: AvailabilityCache,
    site_id: str,
    cloud_name: str,
    poll_interval: float,
    site_timeout: float,
    error_backoff: float,
) -> None:
    while True:
        try:
            await _sync_site(cache, site_id, cloud_name, site_timeout)
            await asyncio.sleep(poll_interval)
        except Exception:  # pylint: disable=broad-exception-caught
            LOG.exception("Availability sync failed for site %s, backing off", site_id)
            await asyncio.sleep(error_backoff)


async def _sync_site(
    cache: AvailabilityCache,
    site_id: str,
    cloud_name: str,
    site_timeout: float,
) -> None:
    LOG.info("Starting availability sync for site %s", site_id)
    loop = asyncio.get_running_loop()

    def _fetch():
        client = BlazarClient(cloud_name)
        return client.list_host_allocations()

    nodes, known_uuids, unavailable_uuids = await asyncio.wait_for(
        loop.run_in_executor(None, _fetch),
        timeout=site_timeout,
    )
    await cache.update_site(site_id, nodes, known_uuids, unavailable_uuids)
    LOG.info("Synced availability for site %s: %d nodes", site_id, len(known_uuids))
