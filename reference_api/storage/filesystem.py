"""File-backed repository helpers for reading JSON data and version info
"""
import json

from pathlib import Path
from typing import Optional, List, Dict, Any

from cachetools import LRUCache, cached
from reference_api.storage import git_versioning


json_cache: LRUCache = LRUCache(maxsize=1024)


@cached(json_cache)
def _read_json(path: Path) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def read_root(ref_dir: Path) -> Optional[Dict]:
    p = ref_dir / "chameleoncloud.json"
    return _read_json(p)


def list_sites(ref_dir: Path) -> List[Dict]:
    sites_dir = ref_dir / "sites"
    if not sites_dir.exists():
        return []
    items = []
    for site_path in sites_dir.iterdir():
        if not site_path.is_dir():
            continue
        site = site_path / f"{site_path.name}.json"
        if site and site.exists():
            data = _read_json(site)
            if data:
                items.append(data)
    return items


def read_site(ref_dir: Path, site_id: str) -> Optional[Dict]:
    relative_path = _get_site_path(site_id)
    return _read_json(ref_dir / relative_path)


def _get_site_path(site_id: str) -> str:
    """
    Returns the relative path to a site's JSON file from the data root.
    """
    return f"sites/{site_id}/{site_id}.json"


def list_clusters(ref_dir: Path, site_id: str) -> Optional[List[Dict]]:
    p = ref_dir / "sites" / site_id / "clusters"
    if not p.exists():
        return []
    items = []
    for cluster_dir in p.iterdir():
        if cluster_dir.is_dir():
            cluster = cluster_dir / f"{cluster_dir.name}.json"
            if cluster.exists():
                data = _read_json(cluster)
                if data:
                    items.append(data)
    return items


def read_cluster(
        ref_dir: Path,
        site_id: str,
        cluster_id: str) -> Optional[Dict]:
    relative_path = get_cluster_path(site_id, cluster_id)
    return _read_json(ref_dir / relative_path)


def get_cluster_path(site_id: str, cluster_id: str) -> str:
    """
    Returns the relative path to a cluster's JSON file from the data root.
    """
    return f"sites/{site_id}/clusters/{cluster_id}/{cluster_id}.json"


def list_nodes(
        ref_dir: Path,
        site_id: str,
        cluster_id: str
) -> Optional[List[Dict]]:
    nodes_dir = ref_dir / "sites" / site_id / "clusters" / cluster_id / "nodes"
    if not nodes_dir.exists():
        return []
    items = []
    for node_file in nodes_dir.glob("*.json"):
        data = _read_json(node_file)
        if data:
            items.append(data)
    return items


def read_node(
        ref_dir: Path,
        site_id: str,
        cluster_id: str,
        node_id: str
) -> Optional[Dict]:
    relative_path = get_node_path(site_id, cluster_id, node_id)
    return _read_json(ref_dir / relative_path)


def get_node_path(site_id: str, cluster_id: str, node_id: str) -> str:
    """
    Returns the relative path to a node's JSON file from the data root.
    """
    return f"sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}.json"


def get_version(repo_path: Path) -> Optional[str]:
    return git_versioning.get_version(repo_path)


def list_versions(
    repo_path: Path, dir_path: Optional[Path] = None
) -> List[Dict]:
    """Return list of git versions from git for the source repository or directory."""
    return git_versioning.list_versions(repo_path, dir_path)


def get_version_info(
    repo_path: Path, version_id: str, dir_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Get detailed version information for a repository or directory."""
    return git_versioning.get_version_info(repo_path, version_id, dir_path)


def get_release_and_timestamp(repo_path: Path) -> Dict[str, Optional[str]]:
    return git_versioning.get_release_and_timestamp(repo_path)
