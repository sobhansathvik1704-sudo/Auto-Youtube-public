"""Tests for video-job endpoints (/api/video-jobs/*)."""

import pytest


_PROJECT_PAYLOAD = {
    "name": "Jobs Test Project",
    "niche": "tech",
    "primary_language": "en",
    "default_format": "short",
}

_JOB_PAYLOAD_TEMPLATE = {
    "topic": "Introduction to Python",
    "category": "tech",
    "audience_level": "beginner",
    "language_mode": "te-en",
    "video_format": "short",
    "duration_seconds": 60,
}


@pytest.fixture()
def project_id(client, auth_headers):
    """Create a project and return its ID."""
    response = client.post("/api/projects", json=_PROJECT_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    return response.json()["id"]


def test_create_video_job_success(client, auth_headers, project_id, mocker):
    """Creating a video job should return 201 and queue a Celery task."""
    mocker.patch("app.api.routes.video_jobs.enqueue_video_job")

    payload = {**_JOB_PAYLOAD_TEMPLATE, "project_id": project_id}
    response = client.post("/api/video-jobs", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["topic"] == "Introduction to Python"
    assert data["status"] == "queued"
    assert "id" in data


def test_create_video_job_requires_auth(client, project_id):
    payload = {**_JOB_PAYLOAD_TEMPLATE, "project_id": project_id}
    response = client.post("/api/video-jobs", json=payload)
    assert response.status_code == 401


def test_create_video_job_invalid_project(client, auth_headers, mocker):
    mocker.patch("app.api.routes.video_jobs.enqueue_video_job")

    payload = {**_JOB_PAYLOAD_TEMPLATE, "project_id": "nonexistent-project"}
    response = client.post("/api/video-jobs", json=payload, headers=auth_headers)
    assert response.status_code == 404


def test_list_video_jobs(client, auth_headers, project_id, mocker):
    mocker.patch("app.api.routes.video_jobs.enqueue_video_job")

    payload = {**_JOB_PAYLOAD_TEMPLATE, "project_id": project_id}
    client.post("/api/video-jobs", json=payload, headers=auth_headers)

    response = client.get("/api/video-jobs", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_list_video_jobs_requires_auth(client):
    response = client.get("/api/video-jobs")
    assert response.status_code == 401


def test_get_video_job_status(client, auth_headers, project_id, mocker):
    mocker.patch("app.api.routes.video_jobs.enqueue_video_job")

    payload = {**_JOB_PAYLOAD_TEMPLATE, "project_id": project_id}
    create_resp = client.post("/api/video-jobs", json=payload, headers=auth_headers)
    job_id = create_resp.json()["id"]

    response = client.get(f"/api/video-jobs/{job_id}/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "job" in data
    assert "events" in data
    assert data["job"]["id"] == job_id


def test_get_video_job_not_found(client, auth_headers):
    response = client.get("/api/video-jobs/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


def test_get_video_job_requires_auth(client, auth_headers, project_id, mocker):
    mocker.patch("app.api.routes.video_jobs.enqueue_video_job")

    payload = {**_JOB_PAYLOAD_TEMPLATE, "project_id": project_id}
    create_resp = client.post("/api/video-jobs", json=payload, headers=auth_headers)
    job_id = create_resp.json()["id"]

    response = client.get(f"/api/video-jobs/{job_id}")
    assert response.status_code == 401
