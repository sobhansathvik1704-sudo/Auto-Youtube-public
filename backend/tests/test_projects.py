"""Tests for project endpoints (/api/projects/*)."""


_PROJECT_PAYLOAD = {
    "name": "My Test Project",
    "niche": "tech",
    "primary_language": "en",
    "secondary_language": None,
    "default_format": "short",
}


def test_create_project_success(client, auth_headers):
    response = client.post("/api/projects", json=_PROJECT_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Test Project"
    assert data["niche"] == "tech"
    assert "id" in data


def test_create_project_requires_auth(client):
    response = client.post("/api/projects", json=_PROJECT_PAYLOAD)
    assert response.status_code == 401


def test_list_projects_returns_created(client, auth_headers):
    # Create a project first
    client.post("/api/projects", json=_PROJECT_PAYLOAD, headers=auth_headers)

    response = client.get("/api/projects", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_list_projects_requires_auth(client):
    response = client.get("/api/projects")
    assert response.status_code == 401


def test_get_project_success(client, auth_headers):
    create_resp = client.post("/api/projects", json=_PROJECT_PAYLOAD, headers=auth_headers)
    project_id = create_resp.json()["id"]

    response = client.get(f"/api/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == project_id


def test_get_project_not_found(client, auth_headers):
    response = client.get("/api/projects/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


def test_get_project_requires_auth(client, auth_headers):
    create_resp = client.post("/api/projects", json=_PROJECT_PAYLOAD, headers=auth_headers)
    project_id = create_resp.json()["id"]

    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 401
