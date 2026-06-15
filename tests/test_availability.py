import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from reference_api.availability.blazar_client import _parse_dt
from reference_api.availability.cache import AvailabilityCache
from reference_api.availability.models import Interval

NODE_UUID = "03129bbe-330c-4591-bc17-96d7e15d3e74"   # gpu_rtx_6000, gpu, x86_64, 128 GiB, no IB
NODE_UUID_2 = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"  # compute_haswell, no gpu, aarch64, 64 GiB, IB
AVAILABILITY_URL = f"/sites/uc/clusters/chameleon/nodes/{NODE_UUID}/availability"

FUTURE = (
    datetime(2099, 1, 1, tzinfo=timezone.utc),
    datetime(2099, 1, 2, tzinfo=timezone.utc),
)

_NOW = datetime.now(timezone.utc)
ACTIVE = (_NOW - timedelta(hours=1), _NOW + timedelta(hours=1))

ALL_KNOWN = frozenset({NODE_UUID, NODE_UUID_2})


def _make_client(mock_ref_dir, tmp_repo_dir, cache):
    from reference_api.main import app, get_availability_cache, get_ref_dir, get_repo_root

    app.dependency_overrides[get_repo_root] = lambda: tmp_repo_dir / "reference-repository"
    app.dependency_overrides[get_ref_dir] = lambda: mock_ref_dir
    app.dependency_overrides[get_availability_cache] = lambda: cache
    return TestClient(app)


@pytest.fixture
def empty_cache():
    return AvailabilityCache()


@pytest.fixture
def seeded_cache():
    cache = AvailabilityCache()
    asyncio.run(cache.update_site("uc", {NODE_UUID: [Interval(*FUTURE)]}, ALL_KNOWN, frozenset()))
    return cache


@pytest.fixture
def synced_empty_cache():
    """Site synced but node has no reservations."""
    cache = AvailabilityCache()
    asyncio.run(cache.update_site("uc", {}, ALL_KNOWN, frozenset()))
    return cache


@pytest.fixture
def active_cache():
    """Node has a reservation that is currently active (started in past, ends in future)."""
    cache = AvailabilityCache()
    asyncio.run(cache.update_site("uc", {NODE_UUID: [Interval(*ACTIVE)]}, ALL_KNOWN, frozenset()))
    return cache


def test_node_availability_not_synced(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get(AVAILABILITY_URL).status_code == 404


def test_node_availability_node_not_in_repo(mock_ref_dir, tmp_repo_dir, seeded_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, seeded_cache)
    assert client.get("/sites/uc/clusters/chameleon/nodes/nonexistent/availability").status_code == 404


def test_node_availability_node_not_in_blazar(mock_ref_dir, tmp_repo_dir):
    # Node exists in the repo but wasn't returned by Blazar — should be 404
    cache = AvailabilityCache()
    asyncio.run(cache.update_site("uc", {}, frozenset(), frozenset()))
    client = _make_client(mock_ref_dir, tmp_repo_dir, cache)
    assert client.get(AVAILABILITY_URL).status_code == 404


def test_node_availability_maintenance(mock_ref_dir, tmp_repo_dir):
    cache = AvailabilityCache()
    asyncio.run(cache.update_site("uc", {}, ALL_KNOWN, ALL_KNOWN))  # all nodes in maintenance
    client = _make_client(mock_ref_dir, tmp_repo_dir, cache)
    r = client.get(AVAILABILITY_URL)
    assert r.status_code == 200
    assert r.json()["maintenance"] is True
    assert r.json()["reservations"] == []


def test_node_availability_free_node_returns_empty(mock_ref_dir, tmp_repo_dir, synced_empty_cache):
    # Free node: site is synced but Blazar has no reservations — should be 200 with empty list, not 404.
    client = _make_client(mock_ref_dir, tmp_repo_dir, synced_empty_cache)
    r = client.get(AVAILABILITY_URL)
    assert r.status_code == 200
    assert r.json()["reservations"] == []


def test_node_availability_with_reservations(mock_ref_dir, tmp_repo_dir, seeded_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, seeded_cache)
    r = client.get(AVAILABILITY_URL)
    assert r.status_code == 200
    j = r.json()
    assert j["node_id"] == NODE_UUID
    assert j["site_id"] == "uc"
    assert j["cluster_id"] == "chameleon"
    assert len(j["reservations"]) == 1
    assert j["reservations"][0]["start"] == "2099-01-01T00:00:00Z"


def test_search_unknown_when_cache_empty(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    r = client.get("/nodes/search")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 2
    assert all(item["availability"] == "unknown" for item in j["items"])


def test_search_node_type_filter(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?node_type=gpu_rtx_6000").json()["total"] == 1
    assert client.get("/nodes/search?node_type=compute_skylake").json()["total"] == 0


def test_search_excludes_busy_node(mock_ref_dir, tmp_repo_dir, seeded_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, seeded_cache)
    r = client.get("/nodes/search?start=2099-01-01T06:00:00Z&end=2099-01-01T18:00:00Z")
    j = r.json()
    assert j["total"] == 1
    assert j["items"][0]["uid"] == NODE_UUID_2


def test_search_includes_node_outside_window(mock_ref_dir, tmp_repo_dir, seeded_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, seeded_cache)
    r = client.get("/nodes/search?start=2098-01-01T00:00:00Z&end=2098-12-31T00:00:00Z")
    assert r.json()["total"] == 2


def test_search_requires_both_start_and_end(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?start=2099-01-01T00:00:00Z").status_code == 400
    assert client.get("/nodes/search?end=2099-01-01T00:00:00Z").status_code == 400


def test_search_site_id_filter(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?site_id=uc").json()["total"] == 2
    assert client.get("/nodes/search?site_id=tacc").json()["total"] == 0


def test_search_gpu_filter(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?gpu=true").json()["total"] == 1
    assert client.get("/nodes/search?gpu=false").json()["total"] == 1


def test_search_arch_filter(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?arch=x86_64").json()["total"] == 1
    assert client.get("/nodes/search?arch=aarch64").json()["total"] == 1
    assert client.get("/nodes/search?arch=sparc").json()["total"] == 0


def test_search_infiniband_filter(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?infiniband=true").json()["total"] == 1
    assert client.get("/nodes/search?infiniband=false").json()["total"] == 1


def test_search_min_ram_filter(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/nodes/search?min_ram=1").json()["total"] == 2
    assert client.get("/nodes/search?min_ram=137438953472").json()["total"] == 1  # 128 GiB threshold
    assert client.get("/nodes/search?min_ram=999999999999999").json()["total"] == 0


def test_search_maintenance_status(mock_ref_dir, tmp_repo_dir):
    cache = AvailabilityCache()
    asyncio.run(cache.update_site("uc", {}, ALL_KNOWN, frozenset({NODE_UUID})))
    client = _make_client(mock_ref_dir, tmp_repo_dir, cache)
    r = client.get("/nodes/search")
    items = {item["uid"]: item for item in r.json()["items"]}
    assert items[NODE_UUID]["availability"] == "maintenance"
    assert items[NODE_UUID_2]["availability"] == "available"


def test_search_future_reservation_shows_available(mock_ref_dir, tmp_repo_dir, seeded_cache):
    # A node with only future reservations is currently available.
    client = _make_client(mock_ref_dir, tmp_repo_dir, seeded_cache)
    r = client.get("/nodes/search")
    items = {item["uid"]: item for item in r.json()["items"]}
    assert items[NODE_UUID]["availability"] == "available"
    assert items[NODE_UUID_2]["availability"] == "available"


def test_search_active_reservation_shows_reserved(mock_ref_dir, tmp_repo_dir, active_cache):
    # A node with a currently-active reservation shows as reserved.
    client = _make_client(mock_ref_dir, tmp_repo_dir, active_cache)
    r = client.get("/nodes/search")
    items = {item["uid"]: item for item in r.json()["items"]}
    assert items[NODE_UUID]["availability"] == "reserved"
    assert items[NODE_UUID_2]["availability"] == "available"


def test_site_availability_not_synced(mock_ref_dir, tmp_repo_dir, empty_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, empty_cache)
    assert client.get("/sites/uc/availability").status_code == 404


def test_site_availability_synced(mock_ref_dir, tmp_repo_dir, seeded_cache):
    client = _make_client(mock_ref_dir, tmp_repo_dir, seeded_cache)
    r = client.get("/sites/uc/availability")
    assert r.status_code == 200
    j = r.json()
    assert j["site_id"] == "uc"
    assert "last_synced" in j
    assert j["synced_node_count"] == 1


def test_parse_dt_returns_utc_aware():
    dt = _parse_dt("2025-03-13T19:35:00.000000")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt == datetime(2025, 3, 13, 19, 35, 0, tzinfo=timezone.utc)


def test_parse_dt_none_input():
    assert _parse_dt(None) is None
    assert _parse_dt("") is None


def test_parse_dt_no_microseconds():
    dt = _parse_dt("2025-03-13T19:35:00")
    assert dt == datetime(2025, 3, 13, 19, 35, 0, tzinfo=timezone.utc)


def test_parse_dt_bad_format():
    assert _parse_dt("not-a-date") is None
