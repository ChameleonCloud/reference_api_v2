"""Utility functions for helping with git versioning
"""
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from cachetools import LRUCache, cached
from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import BadName


git_cache: LRUCache = LRUCache(maxsize=1024)


def get_version(repo_path: Path) -> Optional[str]:
    """Return the git HEAD sha for the provided repo_path"""
    repo = Repo(repo_path, search_parent_directories=True)
    return repo.head.commit.hexsha


def _get_relative_dir_path(repo_root: Path, dir_path: Path) -> Optional[str]:
    """Get directory path relative to repo root or data directory"""
    return str(dir_path.relative_to(repo_root))


@cached(git_cache)
def list_versions(
    repo_path: Path,
    dir_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """List versions for a directory in the repository.
    """
    try:
        repo = Repo(repo_path, search_parent_directories=True)
        repo_root = Path(repo.working_dir)

        if dir_path:
            # Get directory path relative to repo root
            relative_path = _get_relative_dir_path(repo_root, dir_path)
            if not relative_path:
                return []

            # Get history for the path
            log_output = repo.git.log(
                "--",
                relative_path,
                pretty="format:%H,%an,%at,%s",
            )
        else:
            # If no dir_path specified, get repository history,
            # this is for everything, e.g. /versions endpoint
            log_output = repo.git.log(
                pretty="format:%H,%an,%at,%s",
            )

        if not log_output:
            return []

        commits = []
        for line in log_output.strip().split("\n"):
            parts = line.split(",", 3)
            if len(parts) == 4:
                sha, author, timestamp, message = parts
                dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                commits.append({
                    "uid": sha,
                    "message": message.strip(),
                    "date": dt.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    "author": author,
                    "type": "version"
                })
        return commits

    except (InvalidGitRepositoryError, NoSuchPathError, GitCommandError):
        return []


@cached(git_cache)
def get_version_info(
    repo_path: Path,
    version_id: str,
    dir_path: Optional[Path] = None
) -> Optional[Dict[str, str]]:
    """Get detailed information about a specific version."""
    try:
        repo = Repo(repo_path, search_parent_directories=True)
        commit: Any = None

        if dir_path:
            repo_root = Path(repo.working_dir)
            relative_path = _get_relative_dir_path(repo_root, dir_path)
            if not relative_path:
                return None

            # Get the latest commit that affected this path
            log_output = repo.git.log("-1", "--", relative_path, pretty="format:%H")

            if not log_output:
                return None

            # This is the latest commit for this path
            latest_commit = repo.commit(log_output.strip())

            # If version_id was requested, verify it's in the history of this path
            if version_id != latest_commit.hexsha:
                path_history = repo.git.log("--pretty=format:%H", "--", relative_path).split("\n")
                if version_id not in path_history:
                    # If requested version not found, use the latest version for this path
                    commit = latest_commit
                else:
                    commit = repo.commit(version_id)
            else:
                commit = latest_commit

        if not dir_path and version_id:
            commit = repo.commit(version_id)

        if not commit:
            return None

        commit_dt = commit.committed_datetime
        commit_dt_utc = commit_dt.astimezone(timezone.utc)
        date_str = commit_dt_utc.strftime("%a, %d %b %Y %H:%M:%S GMT")
        return {
            "uid": commit.hexsha,
            "message": commit.message.strip(),
            "date": date_str,
            "author": commit.author.name,
            "type": "version"
        }
    except (InvalidGitRepositoryError, NoSuchPathError, BadName, GitCommandError):
        return None


@cached(git_cache)
def get_release_and_timestamp(repo_path: Path) -> Dict[str, Optional[str]]:
    """Get the current release (HEAD sha) and timestamp for the repo."""
    result: Dict[str, Optional[str]] = {"version": None, "timestamp": None}
    try:
        repo = Repo(repo_path, search_parent_directories=True)
        head = repo.head.commit
        result["version"] = head.hexsha
        result["timestamp"] = str(head.committed_date)
    except (InvalidGitRepositoryError, NoSuchPathError, ValueError):
        pass
    return result
