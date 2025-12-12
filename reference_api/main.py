import tomllib

from functools import lru_cache
from pathlib import Path

from typing import List, Optional, Dict
from fastapi import Depends, FastAPI, HTTPException, Path as FastApiPath, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from git import InvalidGitRepositoryError, Repo
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from reference_api.api import collections, items
from reference_api.services import clusters, nodes, site_root, sites


# pylint: disable=too-few-public-methods
class JsonExtensionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith(".json"):
            request.scope["path"] = request.scope["path"][:-5]
        response = await call_next(request)
        return response


app = FastAPI(
    title="Reference API",
    description="Serves reference-repository JSON files as a REST API."
)
app.add_middleware(JsonExtensionMiddleware)

# Mount the UI.
# Note: We mount it at /ui.
ui_path = Path(__file__).resolve().parents[1] / "ui"
app.mount("/ui", StaticFiles(directory=ui_path, html=True), name="ui")


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
    "/nodes/facets",
    response_model=Dict[str, List[str]],
    summary="Get available filter options for nodes",
    tags=["Nodes", "Search"],
)
def get_node_facets(
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    """
    Returns unique values for node properties like 'node_types' and 'gpu_models'
    to populate search filters.
    """
    return nodes.get_node_facets(ref_dir, repo_root)


@app.get(
    "/nodes",
    response_model=List[items.NodeItem],
    summary="Search nodes across all sites",
    tags=["Nodes", "Search"],
)
def search_nodes(
    min_gpu: Optional[int] = Query(None, description="Minimum number of GPUs", ge=0),
    min_ram_gb: Optional[int] = Query(None, description="Minimum RAM in GiB", ge=0),
    architecture: Optional[str] = Query(None, description="CPU Architecture (e.g. x86_64)"),
    node_type: Optional[str] = Query(None, description="Detailed Node Type"),
    gpu_model: Optional[str] = Query(None, description="GPU Model Name (partial match)"),
    ref_dir: Path = Depends(get_ref_dir),
    repo_root: Path = Depends(get_repo_root)
):
    """
    Search for nodes matching specific criteria across all known sites and clusters.
    """
    return nodes.get_all_nodes(
        ref_dir,
        repo_root,
        min_gpu_count=min_gpu,
        min_ram_gb=min_ram_gb,
        architecture=architecture,
        node_type=node_type,
        gpu_model=gpu_model
    )


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
