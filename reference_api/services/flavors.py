"""Flavor-related service functions for the Reference API.
"""
from pathlib import Path
from typing import List, Dict, Optional, Any

from reference_api.api import collections, items
from reference_api.services import utils
from reference_api.storage import filesystem


def _create_flavor_item_from_data(
    flavor_data: Dict[str, Any],
    meta: Dict[str, Optional[str]],
    site_id: str,
) -> items.FlavorItem:
    """Creates a FlavorItem from the raw flavor data."""
    flavor_id = flavor_data.get("uid", "")
    flavor_item = items.FlavorItem(**flavor_data)
    flavor_item.version = meta.get("version")
    flavor_item.links = utils.make_item_links(
        "flavor", site_id, item_id=flavor_id, version=flavor_item.version
    )
    return flavor_item


def _get_flavors_for_site(
    ref_dir: Path,
    site_id: str,
    repo_root: Path,
) -> Optional[List[items.FlavorItem]]:
    """Get all flavors for a given site."""
    meta = utils.get_version_meta(repo_root)
    flavors_json = filesystem.list_flavors(ref_dir, site_id)
    if flavors_json is None:
        return None

    return [
        _create_flavor_item_from_data(f_json, meta, site_id)
        for f_json in flavors_json
    ]


def get_flavor_details(
    ref_dir: Path, site_id: str, flavor_id: str, repo_root: Path
) -> Optional[items.FlavorItem]:
    """Get detailed information for a single flavor."""
    flavor_json = filesystem.read_flavor(ref_dir, site_id, flavor_id)
    if not flavor_json:
        return None

    meta = utils.get_version_meta(repo_root)
    return _create_flavor_item_from_data(flavor_json, meta, site_id)


def get_flavors_collection(
    ref_dir: Path, site_id: str, repo_root: Path, offset: int, limit: int
) -> Optional[collections.FlavorCollection]:
    """Get collection of flavors for a site."""
    return utils.build_paginated_response(
        fetch_func=_get_flavors_for_site,
        fetch_args=(ref_dir, site_id, repo_root),
        offset=offset,
        limit=limit,
        repo_root=repo_root,
        links=utils.make_collection_links("flavors", site_id),
        model_class=collections.FlavorCollection,
    )


def get_versions_for_all_flavors_in_site(
    ref_dir: Path, repo_root: Path, site_id: str, offset: int, limit: int
) -> collections.VersionCollection:
    """Return versions dict for all flavors in a site."""
    flavors_dir = ref_dir / "sites" / site_id / "flavors"
    parent_href = f"/sites/{site_id}/flavors"
    parent_collection_href = f"/sites/{site_id}"
    return utils.get_versions_for_item(
        repo_root, flavors_dir, parent_href, parent_collection_href, offset, limit
    )


def get_versions_for_flavor(
    ref_dir: Path, repo_root: Path, site_id: str, flavor_id: str, offset: int, limit: int
) -> collections.VersionCollection:
    """Return versions dict for a specific flavor."""
    parent_href = f"/sites/{site_id}/flavors/{flavor_id}"
    flavor_path = utils.get_flavor_path(ref_dir, site_id, flavor_id)
    return utils.get_versions_for_item(
        repo_root, flavor_path, parent_href, parent_href, offset, limit
    )


def get_version_info_for_flavor(
    ref_dir: Path, repo_root: Path, site_id: str, flavor_id: str, version_id: str
) -> Optional[Dict]:
    """Gets version information for a specific flavor."""
    flavor_path = utils.get_flavor_path(ref_dir, site_id, flavor_id)
    parent_href = f"/sites/{site_id}/flavors/{flavor_id}"
    return utils.get_version_info_for_item(
        repo_root, flavor_path, parent_href, version_id
    )
