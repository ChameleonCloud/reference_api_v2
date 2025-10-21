from pathlib import Path
from typing import List, Dict, Optional, Any

from reference_api.api import collections
from reference_api.storage import filesystem


def get_version_meta(repo_root: Path) -> Dict[str, Optional[str]]:
    """Get repository version and timestamp."""
    return filesystem.get_release_and_timestamp(repo_root)


def get_item_path(
    ref_dir: Path,
    item_type: str,
    site_id: str,
    cluster_id: Optional[str] = None,
    node_id: Optional[str] = None,
) -> Path:
    """Helper to construct the path to a specific item directory or file."""
    base_path = ref_dir / "sites" / site_id
    if item_type == "site":
        return base_path

    if not cluster_id:
        raise ValueError("cluster_id is required for cluster and node item types")

    cluster_path = base_path / "clusters" / cluster_id
    if item_type == "cluster":
        return cluster_path

    node_path = cluster_path / "nodes"
    if item_type == "node":
        if node_id:
            return node_path / f"{node_id}.json"
        return node_path

    raise ValueError(f"Unknown item_type: {item_type}")


def get_versions_for_item(
    repo_root: Path,
    item_path: Path,
    parent_href: str,
    parent_collection_href: str,
    offset: int,
    limit: int,
) -> collections.VersionCollection:
    """Generic helper to get a paginated version collection for any item."""

    def fetch_all_versions():
        all_versions = filesystem.list_versions(repo_root, dir_path=item_path)
        for v in all_versions:
            v["type"] = "version"
            v["links"] = [
                {
                    "rel": "self",
                    "href": f"{parent_href}/versions/{v['uid']}",
                },
                {
                    "rel": "parent",
                    "href": parent_href,
                },
            ]
        return all_versions

    return build_paginated_response(
        fetch_func=fetch_all_versions,
        fetch_args=(),
        offset=offset,
        limit=limit,
        repo_root=repo_root,
        links=[
            {"rel": "self", "href": f"{parent_href}/versions"},
            {"rel": "parent", "href": parent_collection_href},
        ],
        model_class=collections.VersionCollection,
    )


def get_version_info_for_item(
    repo_root: Path, item_path: Path, parent_href: str, version_id: str
) -> Optional[Dict]:
    """Generic helper to get version info for any item."""
    version_info = filesystem.get_version_info(
        repo_root, version_id, dir_path=item_path
    )
    if version_info:
        version_info["links"] = [
            {"rel": "self", "href": f"{parent_href}/versions/{version_id}"},
            {"rel": "parent", "href": parent_href},
        ]
    return version_info


def make_item_links(
    item_type: str,
    site_id: str,
    cluster_id: Optional[str] = None,
    node_id: Optional[str] = None,
    version: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Helper to generate links for an item."""
    links = []
    if item_type == "site":
        base_href = f"/sites/{site_id}"
        links.extend(
            [
                {"rel": "self", "href": base_href},
                {"rel": "parent", "href": "/"},
                {"rel": "clusters", "href": f"{base_href}/clusters"},
                {"rel": "versions", "href": f"{base_href}/versions"},
            ]
        )
    elif item_type == "cluster":
        base_href = f"/sites/{site_id}/clusters/{cluster_id}"
        links.extend(
            [
                {"rel": "self", "href": base_href},
                {"rel": "parent", "href": f"/sites/{site_id}"},
                {"rel": "nodes", "href": f"{base_href}/nodes"},
                {"rel": "versions", "href": f"{base_href}/versions"},
            ]
        )
    elif item_type == "node":
        base_href = f"/sites/{site_id}/clusters/{cluster_id}/nodes/{node_id}"
        links.extend(
            [
                {"rel": "self", "href": base_href},
                {
                    "rel": "parent",
                    "href": f"/sites/{site_id}/clusters/{cluster_id}",
                },
                {"rel": "versions", "href": f"{base_href}/versions"},
            ]
        )

    if version:
        links.append({"rel": "version", "href": f"{base_href}/versions/{version}"})
    return links


def make_collection_links(
    item_type: str, site_id: str, cluster_id: Optional[str] = None
) -> List[Dict[str, str]]:
    """Helper to generate links for a collection."""
    if item_type == "sites":
        return [
            {"rel": "self", "href": "/sites"},
            {"rel": "parent", "href": "/"},
        ]
    if item_type == "clusters":
        return [
            {"rel": "self", "href": f"/sites/{site_id}/clusters"},
            {"rel": "parent", "href": f"/sites/{site_id}"},
        ]
    if item_type == "nodes":
        return [
            {"rel": "self", "href": f"/sites/{site_id}/clusters/{cluster_id}/nodes"},
            {"rel": "parent", "href": f"/sites/{site_id}/clusters/{cluster_id}"},
        ]
    return []


def build_paginated_response(
    fetch_func: Any,
    fetch_args: tuple,
    offset: int,
    limit: int,
    repo_root: Path,
    links: List[Dict[str, str]],
    model_class: Any,
) -> Any:
    item_list = fetch_func(*fetch_args)
    if item_list is None:
        return None

    paginated_items = item_list[offset : offset + limit]
    version = get_version(repo_root)

    return model_class(
        total=len(item_list),
        offset=offset,
        items=paginated_items,
        version=version,
        links=links,
    )


def get_version(repo_root: Path) -> Optional[str]:
    """Gets the repository version for a given repo_root."""
    return filesystem.get_version(repo_root)
