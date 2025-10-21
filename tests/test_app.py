def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    j = r.json()
    assert j.get("uid") == "chameleoncloud"
    assert "version" in j
    assert "links" in j


def test_sites(client):
    r = client.get("/sites")
    assert r.status_code == 200
    j = r.json()
    assert j.get("total") >= 1
    assert "version" in j
    assert isinstance(j.get("items"), list)


def test_site_detail(client):
    r = client.get("/sites/uc")
    assert r.status_code == 200
    j = r.json()
    assert j.get("uid") == "uc"
    assert "links" in j
    links = {link["rel"]: link["href"] for link in j["links"]}
    assert "versions" in links
    assert "version" in links
    assert links["versions"] == "/sites/uc/versions"
    assert links["version"].startswith("/sites/uc/versions/")


def test_clusters(client):
    r = client.get("/sites/uc/clusters")
    assert r.status_code == 200
    j = r.json()
    assert j.get("total") == 1
    assert "items" in j


def test_cluster_detail(client):
    # Test for a cluster that exists
    r = client.get("/sites/uc/clusters/chameleon")
    assert r.status_code == 200
    j = r.json()
    assert j.get("uid") == "chameleon"
    assert "links" in j
    links = {link["rel"]: link["href"] for link in j["links"]}
    assert "versions" in links
    assert "version" in links
    assert links["versions"] == "/sites/uc/clusters/chameleon/versions"
    assert links["version"].startswith("/sites/uc/clusters/chameleon/versions/")
    # Test for a cluster that does not exist
    r_fail = client.get("/sites/uc/clusters/nonexistent")
    assert r_fail.status_code == 404


def test_all_cluster_versions_for_site(client):
    r = client.get("/sites/uc/clusters/versions")
    assert r.status_code == 200
    j = r.json()
    assert "total" in j
    assert "items" in j
    assert "links" in j
    assert isinstance(j["items"], list)

    links = {link["rel"]: link for link in j["links"]}
    assert links["self"]["href"] == "/sites/uc/clusters/versions"
    assert links["parent"]["href"] == "/sites/uc"
    assert j["total"] > 0


def test_nodes_and_node(client):
    r = client.get("/sites/uc/clusters/chameleon/nodes")
    assert r.status_code == 200
    j = r.json()
    assert j.get("total") == 1
    node_id = j["items"][0]["uid"]
    r2 = client.get(f"/sites/uc/clusters/chameleon/nodes/{node_id}")
    assert r2.status_code == 200


def test_all_site_versions(client):
    r = client.get("/sites/versions")
    assert r.status_code == 200
    j = r.json()
    assert "total" in j
    assert "items" in j
    assert "links" in j
    assert isinstance(j["items"], list)

    links = {link["rel"]: link for link in j["links"]}
    assert links["self"]["href"] == "/sites/versions"
    assert links["parent"]["href"] == "/"


def test_site_versions(client):
    r = client.get("/sites/uc/versions")
    assert r.status_code == 200
    j = r.json()
    assert "total" in j
    assert "items" in j
    assert "links" in j
    assert isinstance(j["items"], list)

    links = {link["rel"]: link for link in j["links"]}
    assert "self" in links
    assert "parent" in links
    assert links["self"]["href"] == "/sites/uc/versions"
    assert links["parent"]["href"] == "/sites"

    if j["total"] > 0:
        version_item = j["items"][0]
        assert "uid" in version_item
        assert "type" in version_item and version_item["type"] == "version"
        assert "links" in version_item

        item_links = {link["rel"]: link for link in version_item["links"]}
        assert "self" in item_links
        assert "parent" in item_links
        assert item_links["self"]["href"] == f"/sites/uc/versions/{version_item['uid']}"
        assert item_links["parent"]["href"] == "/sites/uc"
