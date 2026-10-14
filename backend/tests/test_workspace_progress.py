"""The advisor's per-student progress panel.

It shipped calling the readiness engine with the wrong arguments, so every
request 500'd and the panel never rendered. Nothing exercised the endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import run as seed_run


@pytest.fixture(scope="module", autouse=True)
def seeded() -> None:
    seed_run()


def test_an_advisor_sees_progress_for_every_project_they_oversee() -> None:
    client = TestClient(app)
    token = client.post(
        "/auth/login", json={"email": "mentor@example.edu", "password": "coach1234"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    checked = 0
    for workspace in client.get("/workspaces", headers=headers).json():
        projects = client.get(f"/workspaces/{workspace['id']}/projects", headers=headers)
        if projects.status_code != 200:
            continue
        rows = projects.json()
        rows = rows.get("projects", rows) if isinstance(rows, dict) else rows
        for project in rows:
            pid = project.get("id") or project.get("project_id")
            response = client.get(
                f"/workspaces/{workspace['id']}/projects/{pid}/progress", headers=headers
            )
            assert response.status_code == 200, (pid, response.text)
            body = response.json()
            assert 0 <= body["overall"] <= 100
            assert body["areas"], "progress should break readiness down by area"
            checked += 1
    assert checked >= 3, "the seed should give the advisor several projects to check"
