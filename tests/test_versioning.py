from git import Repo

from reference_api.storage import git_versioning


def test_list_versions_safe(tmp_path):
    # Should return empty list rather than raising if repo not present
    repo_path = tmp_path / "no-repo"
    res = git_versioning.list_versions(repo_path)
    assert isinstance(res, list)


def test_get_version_info_safe(tmp_path):
    repo_path = tmp_path / "no-repo"
    info = git_versioning.get_version_info(repo_path, "abc123")
    assert info is None


def test_release_and_timestamp_safe(tmp_path):
    repo_path = tmp_path / "no-repo"
    rt = git_versioning.get_release_and_timestamp(repo_path)
    assert isinstance(rt, dict)
    assert "version" in rt and "timestamp" in rt


def test_get_release_and_timestamp_from_repo(tmp_path):
    # Create a temporary git repo
    repo_root = tmp_path / "reference-repository"
    repo_root.mkdir(exist_ok=True)
    # create data tree and a file to commit
    data_dir = repo_root / "data" / "chameleoncloud"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / "chameleoncloud.json"
    file_path.write_text('{"uid": "chameleoncloud", "type": "grid"}')

    repo = Repo.init(repo_root)
    repo.index.add([str(file_path)])
    repo.index.commit("Initial commit")

    info = git_versioning.get_release_and_timestamp(repo_root)
    assert info["version"] is not None
    assert info.get("timestamp") is not None


def test_cluster_versions(client):
    """Test cluster version listing endpoint"""
    r = client.get("/sites/uc/clusters/chameleon/versions")
    assert r.status_code == 200
    j = r.json()
    assert "total" in j
    assert "items" in j
    assert "links" in j
    assert isinstance(j["items"], list)

    links = {link["rel"]: link for link in j["links"]}
    assert "self" in links
    assert "parent" in links
    assert links["self"]["href"] == "/sites/uc/clusters/chameleon/versions"
    assert links["parent"]["href"] == "/sites/uc/clusters/chameleon"

    if j["total"] > 0:
        version_item = j["items"][0]
        assert "uid" in version_item
        assert "type" in version_item and version_item["type"] == "version"
        assert "links" in version_item

        item_links = {link["rel"]: link for link in version_item["links"]}
        href_link = f"/sites/uc/clusters/chameleon/versions/{version_item['uid']}"
        assert "self" in item_links
        assert "parent" in item_links
        assert item_links["self"]["href"] == href_link
        assert item_links["parent"]["href"] == "/sites/uc/clusters/chameleon"


def test_node_versions(client):
    """Test node version listing endpoint"""
    # First get a node ID
    r = client.get("/sites/uc/clusters/chameleon/nodes")
    assert r.status_code == 200
    nodes = r.json()
    assert nodes["total"] > 0
    node_id = nodes["items"][0]["uid"]

    r = client.get(f"/sites/uc/clusters/chameleon/nodes/{node_id}/versions")
    assert r.status_code == 200
    j = r.json()
    assert "total" in j
    assert "items" in j
    assert "links" in j
    assert isinstance(j["items"], list)

    links = {link["rel"]: link for link in j["links"]}
    assert "self" in links
    assert "parent" in links
    assert links["self"]["href"] == f"/sites/uc/clusters/chameleon/nodes/{node_id}/versions"
    assert links["parent"]["href"] == f"/sites/uc/clusters/chameleon/nodes/{node_id}"

    if j["total"] > 0:
        version_item = j["items"][0]
        assert "uid" in version_item
        assert "type" in version_item and version_item["type"] == "version"
        assert "links" in version_item

        item_links = {link["rel"]: link for link in version_item["links"]}
        assert "self" in item_links
        assert "parent" in item_links
        base_href = f"/sites/uc/clusters/chameleon/nodes/{node_id}"
        assert item_links["self"]["href"] == f"{base_href}/versions/{version_item['uid']}"
        assert item_links["parent"]["href"] == base_href
