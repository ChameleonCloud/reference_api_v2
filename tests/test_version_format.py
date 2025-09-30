from datetime import datetime
from datetime import timezone

from git import Repo

from reference_api.storage import git_versioning


def setup_test_repo(tmp_path):
    """Helper to create a test repo with some commits"""
    repo_path = tmp_path / "testrepo"
    repo_path.mkdir()
    repo = Repo.init(repo_path)

    # Create a test file and make some commits
    test_file = repo_path / "test.txt"
    test_file.write_text("initial")
    repo.index.add(["test.txt"])
    repo.index.commit("Initial commit", author_date=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))

    test_file.write_text("update 1")
    repo.index.add(["test.txt"])
    repo.index.commit("Update 1", author_date=datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc))

    return repo_path


def test_version_list_format(tmp_path):
    """Test that list_versions returns properly formatted version entries"""
    repo_path = setup_test_repo(tmp_path)
    versions = git_versioning.list_versions(repo_path)

    assert len(versions) == 2  # Should have our 2 test commits
    for v in versions:
        # Check required fields
        assert "uid" in v and v["uid"]  # Has uid, not empty
        assert "type" in v and v["type"] == "version"
        assert "message" in v and v["message"]
        assert "date" in v and v["date"]
        assert "author" in v and v["author"]

        # Check date format (should end with GMT)
        assert v["date"].endswith("GMT")
        # Verify it's parseable
        datetime.strptime(v["date"], "%a, %d %b %Y %H:%M:%S GMT")


def test_version_info_format(tmp_path):
    """Test that get_version_info returns properly formatted version details"""
    repo_path = setup_test_repo(tmp_path)

    # Get first commit's hash
    versions = git_versioning.list_versions(repo_path)
    first_version = versions[-1]["uid"]  # Last in list is first commit

    version_info = git_versioning.get_version_info(repo_path, first_version)
    assert version_info is not None

    # Check required fields
    assert "uid" in version_info
    assert "type" in version_info and version_info["type"] == "version"
    assert "message" in version_info
    assert "date" in version_info
    assert "author" in version_info

    assert version_info["date"].endswith("GMT")
    datetime.strptime(version_info["date"], "%a, %d %b %Y %H:%M:%S GMT")


def test_version_info_for_directory(tmp_path):
    """Test version info when requesting specific directory history"""
    repo_path = setup_test_repo(tmp_path)
    test_dir = repo_path  # Use repo root as test directory since it contains our test.txt

    # Get version info for directory
    versions = git_versioning.list_versions(repo_path, dir_path=test_dir)
    assert len(versions) == 2  # Should see both commits

    # Get specific version
    first_version = versions[-1]["uid"]
    version_info = git_versioning.get_version_info(repo_path, first_version, dir_path=test_dir)
    assert version_info is not None
    assert version_info["type"] == "version"
    assert version_info["message"] == "Initial commit"
