"""Site-related service functions for the Reference API.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional

from reference_api.api import collections, items
from reference_api.services import utils
from reference_api.storage import filesystem


def _create_site_item_from_data(
    site_data: Dict[str, Any], meta: Dict[str, Optional[str]]
) -> items.SiteItem:
    """Creates a SiteItem from the raw site data."""
    site_id = site_data.get("uid", "")
    site_item = items.SiteItem(**site_data)
    site_item.version = meta.get("version")
    site_item.links = utils.make_item_links(
        "site", site_id, version=meta.get("version")
    )
    return site_item


def _get_all_sites(ref_dir: Path, repo_root: Path) -> List[items.SiteItem]:
    """Get a list of all sites from the source json files."""
    meta = utils.get_version_meta(repo_root)
    sites_json = filesystem.list_sites(ref_dir)
    return [_create_site_item_from_data(s_json, meta) for s_json in sites_json]


def get_site_details(
    ref_dir: Path, site_id: str, repo_root: Path
) -> Optional[items.SiteItem]:
    """Get detailed information for a single site from the source json file."""
    site_json = filesystem.read_site(ref_dir, site_id)
    if not site_json:
        return None

    meta = utils.get_version_meta(repo_root)
    return _create_site_item_from_data(site_json, meta)


def get_sites_collection(
    ref_dir: Path, repo_root: Path, offset: int, limit: int
) -> collections.SiteCollection:
    """Get collection of sites with pagination."""
    return utils.build_paginated_response(
        fetch_func=_get_all_sites,
        fetch_args=(ref_dir, repo_root),
        offset=offset,
        limit=limit,
        repo_root=repo_root,
        links=utils.make_collection_links("sites", ""),
        model_class=collections.SiteCollection,
    )


def get_versions_for_all_sites(
    ref_dir: Path, repo_root: Path, offset: int, limit: int
) -> collections.VersionCollection:
    """Return versions dict for all sites."""
    sites_dir = ref_dir / "sites"
    return utils.get_versions_for_item(
        repo_root, sites_dir, "/sites", "/", offset, limit
    )


def get_versions_for_site(
    ref_dir: Path, repo_root: Path, site_id: str, offset: int, limit: int
) -> collections.VersionCollection:
    """Return versions dict for a specific site."""
    site_dir = utils.get_item_path(ref_dir, "site", site_id)
    return utils.get_versions_for_item(
        repo_root, site_dir, f"/sites/{site_id}", "/sites", offset, limit
    )


def get_version_info_for_site(
    ref_dir: Path, repo_root: Path, site_id: str, version_id: str
) -> Optional[Dict]:
    """Gets version information for a specific site."""
    site_dir = utils.get_item_path(ref_dir, "site", site_id)
    return utils.get_version_info_for_item(
        repo_root, site_dir, f"/sites/{site_id}", version_id
    )
