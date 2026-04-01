"""Tests for the PATCH /api/video-jobs/{job_id}/scenes/{scene_id} endpoint."""

import json

import pytest

from app.db.models.scene import Scene
from app.db.models.video_job import VideoJob


_PROJECT_PAYLOAD = {
    "name": "Scene Update Test Project",
    "niche": "tech",
    "primary_language": "en",
    "default_format": "short",
}

_JOB_PAYLOAD = {
    "topic": "Linux processes",
    "category": "tech",
    "audience_level": "beginner",
    "language_mode": "english",
    "video_format": "short",
    "duration_seconds": 30,
}


@pytest.fixture()
def project_id(client, auth_headers):
    resp = client.post("/api/projects", json=_PROJECT_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.fixture()
def job_id(client, auth_headers, project_id, mocker):
    """Create a video job and return its ID (Celery enqueue is mocked)."""
    mocker.patch("app.api.routes.video_jobs.enqueue_video_job")
    payload = {**_JOB_PAYLOAD, "project_id": project_id}
    resp = client.post("/api/video-jobs", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.fixture()
def scene_id(db_session, job_id):
    """Insert a test Scene row directly and set the job to awaiting_approval."""
    job = db_session.get(VideoJob, job_id)
    job.status = "awaiting_approval"
    scene = Scene(
        video_job_id=job_id,
        scene_index=1,
        scene_type="hook",
        narration_text="Original narration.",
        on_screen_text="Original hook",
        visual_prompt="Original prompt",
        asset_config_json=json.dumps({"template": "hook"}),
        duration_ms=3000,
        start_ms=0,
        end_ms=3000,
    )
    db_session.add(scene)
    db_session.commit()
    db_session.refresh(scene)
    return scene.id


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


def test_update_scene_on_screen_text(client, auth_headers, job_id, scene_id):
    payload = {"on_screen_text": "Linux processes: deep dive"}
    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/{scene_id}",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["on_screen_text"] == "Linux processes: deep dive"
    # Other fields must remain unchanged
    assert data["narration_text"] == "Original narration."
    assert data["visual_prompt"] == "Original prompt"


def test_update_scene_narration(client, auth_headers, job_id, scene_id):
    payload = {"narration_text": "Updated narration text."}
    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/{scene_id}",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["narration_text"] == "Updated narration text."


def test_update_scene_visual_prompt(client, auth_headers, job_id, scene_id):
    payload = {"visual_prompt": "htop terminal showing PID list, dark theme"}
    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/{scene_id}",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["visual_prompt"] == "htop terminal showing PID list, dark theme"


def test_update_scene_multiple_fields(client, auth_headers, job_id, scene_id):
    payload = {
        "on_screen_text": "Signals: SIGTERM vs SIGKILL",
        "narration_text": "Linux sends signals to terminate processes.",
        "visual_prompt": "kill command in terminal, SIGTERM signal flow diagram",
    }
    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/{scene_id}",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["on_screen_text"] == "Signals: SIGTERM vs SIGKILL"
    assert data["narration_text"] == "Linux sends signals to terminate processes."
    assert data["visual_prompt"] == "kill command in terminal, SIGTERM signal flow diagram"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_update_scene_requires_auth(client, job_id, scene_id):
    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/{scene_id}",
        json={"on_screen_text": "No auth"},
    )
    assert resp.status_code == 401


def test_update_scene_wrong_job(client, auth_headers, scene_id):
    resp = client.patch(
        f"/api/video-jobs/nonexistent-job/scenes/{scene_id}",
        json={"on_screen_text": "Bad job"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_scene_wrong_scene(client, auth_headers, job_id, scene_id):  # noqa: ARG001
    """Using a nonexistent scene_id while job is awaiting_approval → 404."""
    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/nonexistent-scene",
        json={"on_screen_text": "Bad scene"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_scene_wrong_status(client, auth_headers, db_session, job_id, scene_id):
    """Editing scenes is only allowed while the job is awaiting_approval."""
    job = db_session.get(VideoJob, job_id)
    job.status = "rendering"
    db_session.commit()

    resp = client.patch(
        f"/api/video-jobs/{job_id}/scenes/{scene_id}",
        json={"on_screen_text": "Should fail"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "awaiting approval" in resp.json()["detail"].lower()
