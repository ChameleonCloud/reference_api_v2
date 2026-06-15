import asyncio
import contextlib
import logging
import tomllib

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Path as FastApiPath, Query
from fastapi.responses import JSONResponse
from git import InvalidGitRepositoryError, Repo
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from reference_api.api import collections, items
from reference_api.availability.cache import AvailabilityCache
from reference_api.availability.models import (
    NodeAvailabilityResponse,
    NodeSearchResponse,
    Reservation,
    SearchNodeItem,
)
from reference_api.availability.worker import run_sync_loop
from reference_api.services import clusters, nodes, site_root, sites
from reference_api.storage import filesystem

logging.basicConfig(level=logging.INFO)

LOG = logging.getLogger(__name__)


# pylint: disable=too-few-public-methods
class JsonExtensionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith(".json"):
            request.scope["path"] = request.scope["path"][:-5]
        response = await call_next(request)
        return response


def _load_availability_config(repo_root: Path) -> dict:
    config_path = repo_root.parent / "etc" / "config.toml"
    if not config_path.exists():
        return {"poll_interval": 60.0, "site_timeout": 120.0, "error_backoff": 60.0, "sites": {}}
    try:
        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {"poll_interval": 60.0, "site_timeout": 120.0, "error_backoff": 60.0, "sites": {}}
    avail = cfg.get("availability", {})
    return {
        "poll_interval": float(avail.get("poll_interval_seconds", 60)),
        "site_timeout": float(avail.get("site_timeout_seconds", 120)),
        "error_backoff": float(avail.get("error_backoff_seconds", 60)),
        "sites": {
            site_id: site_cfg["cloud"]
            for site_id, site_cfg in avail.get("sites", {}).items()
        },
    }


@asynccontextmanager
async def lifespan(web_app: FastAPI):
    repo_root = get_repo_root()
    avail_cfg = _load_availability_config(repo_root)
    cache = AvailabilityCache()
    web_app.state.availability_cache = cache

    task = None
    if avail_cfg["sites"]:
        task = asyncio.create_task(
            run_sync_loop(
                cache,
                avail_cfg["sites"],
                avail_cfg["poll_interval"],
                avail_cfg["site_timeout"],
                avail_cfg["error_backoff"],
            )
        )
    else:
        LOG.warning("No availability sites configured; worker not started")

    yield

    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def get_availability_cache(request: Request) -> AvailabilityCache:
    return request.app.state.availability_cache


app = FastAPI(
    title="Reference API",
    description="Serves reference-repository JSON files as a REST API.",
    lifespan=lifespan,
)
app.add_middleware(JsonExtensionMiddleware)


@lru_cache(maxsize=1)
def get_repo_root() -> Path:
    """Find the root directory of the reference-repository git location."""
    try:
        # Find the main project repo root first
        main_repo = Repo(Path(__file__).parent, search_parent_directories=True)
        # The repo for versioning is the submodule
        submodule_repo_path = Path(main_repo.working_dir) / "reference-repository"
        return submodule_repo_path
    except InvalidGitRepositoryError:
        return Path(__file__).resolve().parents[1] / "reference-repository"


@lru_cache(maxsize=1)
def get_ref_dir(repo_root: Path = Depends(get_repo_root)) -> Path:
    """Determine the reference repository data directory."""
    config_path = repo_root.parent / "etc" / "config.toml"
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                cfg = tomllib.load(f)
            if ref_cfg := cfg.get("reference", {}).get("ref_dir"):
                p = Path(ref_cfg)
                project_root = repo_root.parent
                return p if p.is_absolute() else project_root / p
        except (tomllib.TOMLDecodeError, OSError):
            pass

    # default path
    return (repo_root / "data" / "chameleoncloud").resolve()


@app.get(
    "/",
    response_model=dict,
    response_class=JSONResponse,
    summary="Get top-level information about the reference API",
    tags=["General"],
)
def root(ref_dir: Path = Depends(get_ref_dir), repo_root: Path = Depends(get_repo_root)):
    data = site_root.get_root_info(ref_dir, repo_root)
    if not data:
        raise HTTPException(
            status_code=500,
            detail="reference-repository not found"
        )
    return data


@app.get(
    "/sites",
    response_model=collections.SiteCollection,
    summary="List all sites",
    tags=["Sites"],
)
def list_sites(
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    return sites.get_sites_collection(ref_dir, repo_root, offset, limit)


@app.get(
    "/sites/versions",
    response_model=collections.VersionCollection,
    summary="List versions for all sites",
    tags=["Sites", "Versioning"],
)
def list_all_site_versions(
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root),
):
    """Lists all versions that have affected any site."""
    return sites.get_versions_for_all_sites(
        ref_dir, repo_root, offset, limit
    )


@app.get(
    "/sites/{site_id}",
    response_model=items.SiteItem,
    summary="Get a single site by its ID",
    tags=["Sites"],
    responses={404: {"description": "Site not found"}},
)
def get_site(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    site = sites.get_site_details(ref_dir, site_id, repo_root)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@app.get(
    "/sites/{site_id}/versions",
    response_model=collections.VersionCollection,
    summary="List versions for a site",
    tags=["Sites", "Versioning"],
)
def list_site_versions(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    return sites.get_versions_for_site(
        ref_dir, repo_root, site_id, offset, limit
    )


@app.get(
    "/sites/{site_id}/versions/{version_id}",
    response_model=dict,
    summary="Get version details for a site",
    responses={404: {"description": "Version not found"}},
    tags=["Sites", "Versioning"],
)
def get_site_version(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    version_id: str = FastApiPath(
        ..., description="The unique identifier for the version (commit SHA)."
    ),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    v = sites.get_version_info_for_site(
        ref_dir, repo_root, site_id, version_id
    )
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@app.get(
    "/sites/{site_id}/clusters",
    response_model=collections.ClusterCollection,
    summary="List clusters for a site",
    responses={404: {"description": "Site not found"}},
    tags=["Clusters"],
)
def list_clusters(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    collection = clusters.get_clusters_collection(
        ref_dir, site_id, repo_root, offset, limit
    )
    if collection is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return collection


@app.get(
    "/sites/{site_id}/clusters/versions",
    response_model=collections.VersionCollection,
    summary="List versions for all clusters in a site",
    tags=["Clusters", "Versioning"],
)
def list_all_cluster_versions_for_site(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root),
):
    """Lists all versions that have affected any cluster in the site."""
    return clusters.get_versions_for_all_clusters_in_site(
        ref_dir, repo_root, site_id, offset, limit
    )


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}",
    response_model=items.ClusterItem,
    summary="Get a single cluster by its ID",
    responses={404: {"description": "Cluster not found"}},
    tags=["Clusters"],
)
def get_cluster(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    cluster = clusters.get_cluster_details(
        ref_dir, site_id, cluster_id, repo_root
    )
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/versions",
    response_model=collections.VersionCollection,
    summary="List versions for a cluster",
    tags=["Clusters", "Versioning"],
)
def list_cluster_versions(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    return clusters.get_versions_for_cluster(
        ref_dir, repo_root, site_id, cluster_id, offset, limit)


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/versions/{version_id}",
    response_model=dict,
    summary="Get version details for a cluster",
    responses={404: {"description": "Version not found"}},
    tags=["Clusters", "Versioning"],
)
def get_cluster_version(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    version_id: str = FastApiPath(
        ..., description="The unique identifier for the version (commit SHA)."
    ),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    v = clusters.get_version_info_for_cluster(
        ref_dir, repo_root, site_id, cluster_id, version_id
    )
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/nodes",
    response_model=collections.NodeCollection,
    summary="List nodes for a cluster",
    responses={404: {"description": "Site/cluster not found"}},
    tags=["Nodes"],
)
def list_nodes(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    collection = nodes.get_nodes_collection(
        ref_dir, site_id, cluster_id, repo_root, offset, limit
    )
    if collection is None:
        raise HTTPException(status_code=404, detail="Site/cluster not found")
    return collection


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}",
    response_model=items.NodeItem,
    summary="Get a single node by its ID",
    responses={404: {"description": "Node not found"}},
    tags=["Nodes"],
)
def get_node(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    node_id: str = FastApiPath(
        ..., description="The unique identifier for the node."
    ),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    node = nodes.get_node_details(
        ref_dir, site_id, cluster_id, node_id, repo_root
    )
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}/versions",
    response_model=collections.VersionCollection,
    summary="List versions for a node",
    tags=["Nodes", "Versioning"],
)
def list_node_versions(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    node_id: str = FastApiPath(
        ..., description="The unique identifier for the node."
    ),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, gt=0, le=500, description="Limit for pagination"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    return nodes.get_versions_for_node(
        ref_dir, repo_root, site_id, cluster_id, node_id, offset, limit
    )


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}/versions/{version_id}",
    response_model=dict,
    summary="Get version details for a node",
    responses={404: {"description": "Version not found"}},
    tags=["Nodes", "Versioning"],
)
def get_node_version(
    site_id: str = FastApiPath(
        ..., description="The unique identifier for the site.", examples=["uc"]
    ),
    cluster_id: str = FastApiPath(
        ..., description="The unique identifier for the cluster.", examples=["chameleon"]
    ),
    node_id: str = FastApiPath(
        ..., description="The unique identifier for the node."
    ),
    version_id: str = FastApiPath(
        ..., description="The unique identifier for the version (commit SHA)."
    ),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    v = nodes.get_version_info_for_node(
        ref_dir, repo_root, site_id, cluster_id, node_id, version_id
    )
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@app.get(
    "/versions",
    response_model=dict,
    summary="List all versions for the repository",
    tags=["Versioning"],
)
def list_versions(repo_root: Path = Depends(get_repo_root)):
    return site_root.get_versions(repo_root)


@app.get(
    "/versions/{version_id}",
    summary="Get details for a specific repository version",
    tags=["Versioning"],
    responses={404: {"description": "Version not found"}},
)
def get_version(
    version_id: str = FastApiPath(
        ..., description="The unique identifier for the version (commit SHA)."
    ), repo_root: Path = Depends(get_repo_root)
):
    v = site_root.get_version_info(repo_root, version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return v


@app.get(
    "/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}/availability",
    response_model=NodeAvailabilityResponse,
    summary="Get reservation intervals for a node",
    tags=["Nodes", "Availability"],
    responses={404: {"description": "Node not found or availability not yet synced"}},
)
async def get_node_availability(
    site_id: str = FastApiPath(..., examples=["uc"]),
    cluster_id: str = FastApiPath(..., examples=["chameleon"]),
    node_id: str = FastApiPath(...),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root),
    cache: AvailabilityCache = Depends(get_availability_cache),
):
    if not nodes.get_node_details(ref_dir, site_id, cluster_id, node_id, repo_root):
        raise HTTPException(status_code=404, detail="Node not found")
    cached = await cache.get_node(site_id, node_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Availability not yet synced for this node")
    last_synced, intervals, maintenance = cached
    if intervals is None:
        raise HTTPException(status_code=404, detail="Node not registered in Blazar")
    return NodeAvailabilityResponse(
        node_id=node_id,
        cluster_id=cluster_id,
        site_id=site_id,
        last_updated=last_synced,
        maintenance=maintenance,
        reservations=[Reservation(start=iv.start, end=iv.end) for iv in intervals],
    )


@app.get(
    "/sites/{site_id}/availability",
    summary="Get availability sync status for a site",
    tags=["Sites", "Availability"],
    responses={404: {"description": "Site not yet synced"}},
)
async def get_site_availability(
    site_id: str = FastApiPath(..., examples=["tacc"]),
    cache: AvailabilityCache = Depends(get_availability_cache),
):
    result = await cache.get_site_last_synced(site_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Availability not yet synced for this site")
    last_synced, node_count = result
    return {"site_id": site_id, "last_synced": last_synced, "synced_node_count": node_count}


@app.get(
    "/nodes/search",
    response_model=NodeSearchResponse,
    summary="Search nodes by hardware properties and availability window",
    tags=["Nodes", "Availability"],
)
async def search_nodes(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    site_id: Optional[str] = Query(None, description="Filter by site, e.g. tacc or uc"),
    node_type: Optional[str] = Query(None, description="Filter by node type, e.g. compute_skylake"),
    arch: Optional[str] = Query(
        None, description="Filter by CPU architecture, e.g. x86_64 or aarch64"
    ),
    gpu: Optional[bool] = Query(
        None, description="Filter to nodes with (true) or without (false) a GPU"
    ),
    infiniband: Optional[bool] = Query(
        None, description="Filter to nodes with (true) or without (false) InfiniBand"
    ),
    min_ram: Optional[int] = Query(
        None, description="Minimum RAM in bytes, e.g. 137438953472 for 128 GiB"
    ),
    start: Optional[datetime] = Query(
        None, description="Start of desired reservation window (ISO 8601)"
    ),
    end: Optional[datetime] = Query(
        None, description="End of desired reservation window (ISO 8601)"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(500, gt=0, le=500),
    ref_dir: Path = Depends(get_ref_dir),
    cache: AvailabilityCache = Depends(get_availability_cache),
):
    if (start is None) != (end is None):
        raise HTTPException(status_code=400, detail="Provide both start and end, or neither")

    now = datetime.now(timezone.utc)
    results: list[SearchNodeItem] = []
    for site_data in filesystem.list_sites(ref_dir):
        current_site_id = site_data.get("uid")
        if not current_site_id:
            continue
        if site_id and current_site_id != site_id:
            continue
        site_result = await cache.get_site_nodes(current_site_id)
        site_nodes: dict | None = None
        site_unavailable: frozenset = frozenset()
        if site_result is not None:
            site_nodes, site_unavailable = site_result

        for cluster_data in filesystem.list_clusters(ref_dir, current_site_id) or []:
            cluster_id = cluster_data.get("uid")
            if not cluster_id:
                continue

            for node_data in filesystem.list_nodes(ref_dir, current_site_id, cluster_id) or []:
                if node_type and node_data.get("node_type") != node_type:
                    continue
                if arch and node_data.get("architecture", {}).get("platform_type") != arch:
                    continue
                if gpu is not None and node_data.get("gpu", {}).get("gpu", False) != gpu:
                    continue
                node_ib = bool(node_data.get("infiniband", False))
                if infiniband is not None and node_ib != infiniband:
                    continue
                node_ram = node_data.get("main_memory", {}).get("ram_size", 0)
                if min_ram is not None and node_ram < min_ram:
                    continue

                node_uuid = node_data.get("uid")
                if not node_uuid:
                    continue

                availability_until = None
                if site_nodes is None:
                    availability = "unknown"
                elif node_uuid in site_unavailable:
                    availability = "maintenance"
                else:
                    intervals = site_nodes.get(node_uuid, [])
                    if start and end:
                        if any(iv.start < end and iv.end > start for iv in intervals):
                            continue  # busy in requested window
                        availability = "available"
                    else:
                        active = [iv for iv in intervals if iv.start <= now < iv.end]
                        if active:
                            availability = "reserved"
                            availability_until = min(iv.end for iv in active)
                        else:
                            availability = "available"
                            upcoming = [iv.start for iv in intervals if iv.start > now]
                            if upcoming:
                                availability_until = min(upcoming)

                results.append(SearchNodeItem.model_validate({
                    **node_data,
                    "site_id": current_site_id,
                    "cluster_id": cluster_id,
                    "availability": availability,
                    "availability_until": availability_until,
                }))

    return NodeSearchResponse(
        total=len(results),
        offset=offset,
        items=results[offset:offset + limit],
    )
