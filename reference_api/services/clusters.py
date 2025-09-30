"""Cluster-related service functions for the Reference API.
"""
from pathlib import Path
from typing import List, Dict, Optional, Any

from reference_api.api import collections, items
from reference_api.services import utils
from reference_api.storage import filesystem


def _create_cluster_item_from_data(
    cluster_data: Dict[str, Any],
    meta: Dict[str, Optional[str]],
    site_id: str,
) -> items.ClusterItem:
    """Creates a ClusterItem from the raw cluster data."""
    cluster_id = cluster_data.get("uid", "")
    cluster_item = items.ClusterItem(**cluster_data)
    cluster_item.version = meta.get("version")
    cluster_item.links = utils.make_item_links(
        "cluster", site_id, cluster_id, version=cluster_item.version
    )
    if not getattr(cluster_item, "queues", None):
        cluster_item.queues = ["admin", "default"]
    return cluster_item


def _get_clusters_for_site(
    ref_dir: Path,
    site_id: str,
    repo_root: Path,
) -> Optional[List[items.ClusterItem]]:
    """Get all clusters for a given site."""
    meta = utils.get_version_meta(repo_root)
    clusters_json = filesystem.list_clusters(ref_dir, site_id)
    if clusters_json is None:
        return None

    return [
        _create_cluster_item_from_data(c_json, meta, site_id)
        for c_json in clusters_json
    ]


def get_cluster_details(
    ref_dir: Path, site_id: str, cluster_id: str, repo_root: Path
) -> Optional[items.ClusterItem]:
    """Get detailed information for a single cluster."""
    cluster_json = filesystem.read_cluster(ref_dir, site_id, cluster_id)
    if not cluster_json:
        return None

    meta = utils.get_version_meta(repo_root)
    return _create_cluster_item_from_data(cluster_json, meta, site_id)


def get_clusters_collection(
    ref_dir: Path, site_id: str, repo_root: Path, offset: int, limit: int
) -> Optional[collections.ClusterCollection]:
    """Get collection of clusters for a site."""
    return utils.build_paginated_response(
        fetch_func=_get_clusters_for_site,
        fetch_args=(ref_dir, site_id, repo_root),
        offset=offset,
        limit=limit,
        repo_root=repo_root,
        links=utils.make_collection_links("clusters", site_id),
        model_class=collections.ClusterCollection,
    )


def get_versions_for_all_clusters_in_site(
    ref_dir: Path, repo_root: Path, site_id: str, offset: int, limit: int
) -> collections.VersionCollection:
    """Return versions dict for all clusters in a site."""
    clusters_dir = ref_dir / "sites" / site_id / "clusters"
    parent_href = f"/sites/{site_id}/clusters"
    parent_collection_href = f"/sites/{site_id}"
    return utils.get_versions_for_item(
        repo_root, clusters_dir, parent_href, parent_collection_href, offset, limit
    )


def get_versions_for_cluster(
    ref_dir: Path, repo_root: Path, site_id: str, cluster_id: str, offset: int, limit: int
) -> collections.VersionCollection:
    """Return versions dict for a specific cluster."""
    parent_href = f"/sites/{site_id}/clusters/{cluster_id}"
    cluster_dir = utils.get_item_path(ref_dir, "cluster", site_id, cluster_id)
    return utils.get_versions_for_item(
        repo_root, cluster_dir, parent_href, parent_href, offset, limit
    )


def get_version_info_for_cluster(
    ref_dir: Path, repo_root: Path, site_id: str, cluster_id: str, version_id: str
) -> Optional[Dict]:
    """Gets version information for a specific cluster."""
    cluster_dir = utils.get_item_path(ref_dir, "cluster", site_id, cluster_id)
    parent_href = f"/sites/{site_id}/clusters/{cluster_id}"
    return utils.get_version_info_for_item(
        repo_root, cluster_dir, parent_href, version_id
    )
