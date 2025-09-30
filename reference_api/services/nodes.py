"""Node-related service functions for the Reference API.
"""
from pathlib import Path
from typing import List, Dict, Optional, Any

from reference_api.api import collections, items
from reference_api.services import utils
from reference_api.storage import filesystem


def _create_node_item_from_data(
        node_data: Dict[str, Any],
        meta: Dict[str, Optional[str]],
        site_id: str,
        cluster_id: str
) -> items.NodeItem:
    """Creates a NodeItem from the raw node data."""
    node_id = node_data.get("uid", "")
    node_item = items.NodeItem(**node_data)
    node_item.links = utils.make_item_links(
        "node", site_id, cluster_id, node_id, version=meta.get("version")
    )
    node_item.version = meta.get("version")
    return node_item


def _get_nodes_for_cluster(
        ref_dir: Path,
        site_id: str,
        cluster_id: str,
        repo_root: Path
) -> Optional[List[items.NodeItem]]:
    """Get all nodes for a given cluster."""
    nodes_json = filesystem.list_nodes(ref_dir, site_id, cluster_id)
    if nodes_json is None:
        return None

    meta = utils.get_version_meta(repo_root)
    return [
        _create_node_item_from_data(n_json, meta, site_id, cluster_id)
        for n_json in nodes_json
    ]


def get_nodes_collection(
        ref_dir: Path,
        site_id: str,
        cluster_id: str,
        repo_root: Path,
        offset: int,
        limit: int
) -> Optional[collections.NodeCollection]:
    """Get collection of nodes for a cluster."""
    return utils.build_paginated_response(
        fetch_func=_get_nodes_for_cluster,
        fetch_args=(ref_dir, site_id, cluster_id, repo_root),
        offset=offset,
        limit=limit,
        repo_root=repo_root,
        links=utils.make_collection_links("nodes", site_id, cluster_id),
        model_class=collections.NodeCollection
    )


def get_node_details(
        ref_dir: Path,
        site_id: str,
        cluster_id: str,
        node_id: str,
        repo_root: Path
) -> Optional[items.NodeItem]:
    """Get detailed information for a single node."""
    node_json = filesystem.read_node(ref_dir, site_id, cluster_id, node_id)
    if not node_json:
        return None

    meta = utils.get_version_meta(repo_root)
    node_item = _create_node_item_from_data(node_json, meta, site_id, cluster_id)
    return node_item


def get_versions_for_node(
    ref_dir: Path,
    repo_root: Path,
    site_id: str,
    cluster_id: str,
    node_id: str,
    offset: int,
    limit: int
) -> collections.VersionCollection:
    """Return versions dict for a specific node."""
    parent_href = f"/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}"
    node_file_path = utils.get_item_path(ref_dir, "node", site_id, cluster_id, node_id)
    return utils.get_versions_for_item(
        repo_root, node_file_path, parent_href, parent_href, offset, limit
    )


def get_version_info_for_node(
    ref_dir: Path, repo_root: Path, site_id: str, cluster_id: str, node_id: str, version_id: str
) -> Optional[Dict]:
    """Gets version information for a specific node."""
    node_file_path = utils.get_item_path(ref_dir, "node", site_id, cluster_id, node_id)
    parent_href = f"/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}"
    return utils.get_version_info_for_item(
        repo_root, node_file_path, parent_href, version_id
    )
