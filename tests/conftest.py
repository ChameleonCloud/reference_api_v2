import shutil
from pathlib import Path

import pytest
from git import Repo


@pytest.fixture(scope="session")
def tmp_repo_dir(tmp_path_factory):
    """
    Creates a temporary reference repository structure from test data and
    initializes it as a git repository with a single commit.
    """
    root = tmp_path_factory.mktemp("refrepo")
    data_src = Path(__file__).resolve().parent / "data" / "chameleoncloud"
    repo_root = root / "reference-repository"
    data_dst = repo_root / "data" / "chameleoncloud"

    repo = Repo.init(repo_root)
    shutil.copytree(data_src, data_dst, dirs_exist_ok=True)
    repo.index.add(
        [
            "data/chameleoncloud/sites/uc/uc.json",
            "data/chameleoncloud/sites/uc/clusters/chameleon/chameleon.json"
        ]
    )
    repo.index.commit("Initial commit for test repo")

    return root


@pytest.fixture
def mock_ref_dir(tmp_repo_dir):
    """Provides the Path to the mock reference data directory."""
    return tmp_repo_dir / "reference-repository" / "data" / "chameleoncloud"


@pytest.fixture
def client(mock_ref_dir, tmp_repo_dir):
    """
    Provides a TestClient with dependencies overridden for testing.
    - The reference repository path is pointed to our mock data.
    """
    # Import app and dependencies here to ensure mocks are applied
    from reference_api.main import app, get_ref_dir, get_repo_root
    from fastapi.testclient import TestClient

    # Override the dependency to return our mock path
    def get_mock_repo_root():
        return tmp_repo_dir / "reference-repository"

    def get_mock_ref_dir():
        return mock_ref_dir

    app.dependency_overrides[get_repo_root] = get_mock_repo_root
    app.dependency_overrides[get_ref_dir] = get_mock_ref_dir

    return TestClient(app)
