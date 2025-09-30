"""Service functions for the site root and versions endpoints.
"""
from pathlib import Path
from typing import Dict, Any, Optional

from reference_api.services import utils
from reference_api.storage import filesystem


def get_version_info(repo_root: Path, version_id: str) -> Optional[Dict]:
    """Gets version information for a given repo_root and version_id."""
    return filesystem.get_version_info(repo_root, version_id)


def get_versions(repo_root: Path) -> Dict[str, Any]:
    """Return versions dict for the /versions endpoint."""
    versions = filesystem.list_versions(repo_root)
    for v in versions:
        v["links"] = [
            {
                "rel": "self",
                "href": f"/versions/{v['uid']}",
            },
            {
                "rel": "parent",
                "href": "/",
            },
        ]
    return {
        "versions": versions,
        "version": utils.get_version(repo_root),
        "links": [{"rel": "self", "href": "/versions"}, {"rel": "parent", "href": "/"}],
    }


def get_root_info(ref_dir: Path, repo_root: Path) -> Optional[Dict[str, Any]]:
    """Get info for the root endpoint."""
    orig_info = filesystem.read_root(ref_dir)
    if not orig_info:
        return None

    meta = utils.get_version_meta(repo_root)
    info = orig_info.copy()
    info["version"] = meta.get("version")
    info["timestamp"] = meta.get("timestamp")
    info.setdefault("links", [])
    info["links"].extend(
        [
            {"rel": "sites", "href": "/sites"},
            {"rel": "self", "href": "/"},
            {"rel": "parent", "href": "/"},
            {"rel": "versions", "href": "/versions"},
        ]
    )
    return info
