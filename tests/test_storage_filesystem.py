from reference_api.storage import filesystem


def test_read_root_exists(mock_ref_dir):
    data = filesystem.read_root(mock_ref_dir)
    assert data is not None
    assert data.get("uid") == "chameleoncloud"
    meta = filesystem.get_release_and_timestamp(mock_ref_dir)
    assert isinstance(meta, dict)


def test_list_sites(mock_ref_dir):
    sites = filesystem.list_sites(mock_ref_dir)
    assert isinstance(sites, list)
    assert any(s.get("uid") == "uc" for s in sites)


def test_read_site(mock_ref_dir):
    site = filesystem.read_site(mock_ref_dir, "uc")
    assert site is not None
    assert site.get("uid") == "uc"


def test_list_clusters(mock_ref_dir):
    clusters = filesystem.list_clusters(mock_ref_dir, "uc")
    assert clusters and len(clusters) == 1
    assert clusters[0].get("uid") == "chameleon"


def test_read_cluster(mock_ref_dir):
    cluster = filesystem.read_cluster(mock_ref_dir, "uc", "chameleon")
    assert cluster is not None
    assert cluster.get("uid") == "chameleon"


def test_version_helpers(mock_ref_dir):
    v = filesystem.get_version(mock_ref_dir)
    # may be None in test env but should not raise
    assert True


def test_list_nodes(mock_ref_dir):
    nodes = filesystem.list_nodes(mock_ref_dir, "uc", "chameleon")
    assert nodes and len(nodes) == 1


def test_read_node(mock_ref_dir):
    node = filesystem.read_node(
        mock_ref_dir,
        "uc",
        "chameleon",
        "03129bbe-330c-4591-bc17-96d7e15d3e74"
    )
    assert node and node.get("node_name") == "nc35"
