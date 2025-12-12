"""Node-related service functions for the Reference API.
"""
from pathlib import Path
from typing import List, Dict, Optional, Any

from reference_api.api import collections, items
from reference_api.services import utils
from reference_api.storage import filesystem
# Loop import avoidance
import reference_api.services.sites as sites_service
import reference_api.services.clusters as clusters_service


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


def get_all_nodes(
    ref_dir: Path,
    repo_root: Path,
    min_gpu_count: Optional[int] = None,
    min_ram_gb: Optional[int] = None,
    architecture: Optional[str] = None,
    gpu_model: Optional[str] = None,
    node_type: Optional[str] = None,
) -> List[items.NodeItem]:
    """
    Get all nodes across all sites and clusters, optionally filtered.
    Injects site_id and cluster_id into the node item for context.
    """
    all_sites = sites_service._get_all_sites(ref_dir, repo_root) # pylint: disable=protected-access
    results = []

    for site in all_sites:
        # SiteItem has 'uid' usually, but let's be safe
        site_id = getattr(site, "uid", None) or getattr(site, "id", "")
        clusters = clusters_service._get_clusters_for_site(ref_dir, site_id, repo_root) # pylint: disable=protected-access
        
        if not clusters:
            continue

        for cluster in clusters:
            cluster_id = getattr(cluster, "uid", None) or getattr(cluster, "id", "")
            nodes = _get_nodes_for_cluster(ref_dir, site_id, cluster_id, repo_root)
            
            if not nodes:
                continue

            for node in nodes:
                # -- Filtering Logic --
                
                # Node Type
                if node_type and getattr(node, "node_type", "") != node_type:
                    continue

                # Architecture
                if architecture:
                    node_arch = getattr(node, "architecture", {})
                    # platform_type is usually where 'x86_64' etc lives
                    if not node_arch or architecture.lower() not in node_arch.get("platform_type", "").lower():
                         continue

                # RAM
                if min_ram_gb is not None:
                    node_mem = getattr(node, "main_memory", {})
                    # ram_size is bytes. min_ram_gb is GB.
                    size_bytes = node_mem.get("ram_size", 0)
                    if size_bytes < (min_ram_gb * 1024 * 1024 * 1024):
                        continue

                # GPU Count
                node_gpu = getattr(node, "gpu", {})
                if min_gpu_count is not None:
                    count = node_gpu.get("gpu_count", 0) if node_gpu.get("gpu") else 0
                    if count < min_gpu_count:
                        continue
                
                # GPU Model
                if gpu_model:
                    model = node_gpu.get("gpu_model", "") if node_gpu.get("gpu") else ""
                    if not model or gpu_model.lower() not in model.lower():
                        continue
                
                # Inject context
                # NodeItem allows extra fields via ConfigDict
                setattr(node, "site_id", site_id)
                setattr(node, "cluster_id", cluster_id)
                
                results.append(node)
                
    return results


def get_node_facets(ref_dir: Path, repo_root: Path) -> Dict[str, List[str]]:
    """
    Scans all nodes to return available filter values (facets).
    """
    # This effectively scans everything. In a real DB this would be a trivial aggregation.
    # Re-using get_all_nodes without filters to iterate once.
    nodes = get_all_nodes(ref_dir, repo_root)
    
    node_types = set()
    gpu_models = set()
    
    for n in nodes:
        if n.node_type:
            node_types.add(n.node_type)
        
        gpu = getattr(n, "gpu", {})
        if gpu and gpu.get("gpu") and gpu.get("gpu_model"):
            gpu_models.add(gpu.get("gpu_model"))
            
    return {
        "node_types": sorted(list(node_types)),
        "gpu_models": sorted(list(gpu_models))
    }
