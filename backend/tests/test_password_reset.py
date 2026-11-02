"""Forgot password: the emailed one-time link.

What matters most here is what must *not* happen: the form must not reveal
who has an account, a link must not work twice or after it expires, and a
reset must sign out whoever else was using the old password.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.project import utcnow
from app.models.security import PasswordResetToken, RateLimitHit
from app.seed import run as seed_run
from app.services import email as email_service
from app.services import password_reset


@pytest.fixture(scope="module", autouse=True)
def seeded() -> None:
    seed_run()


@pytest.fixture()
def client() -> TestClient:
    with SessionLocal() as db:
        db.execute(delete(RateLimitHit))
        db.commit()
    return TestClient(app)


@pytest.fixture()
def outbox(monkeypatch) -> list[dict]:
    """Capture emails instead of sending them."""

    sent: list[dict] = []

    def fake_send(**message):
        sent.append(message)
        return True

    monkeypatch.setattr(password_reset, "send_email", fake_send)
    return sent


def _new_account(client: TestClient, password: str = "original-pass") -> str:
    email = f"reset.{uuid.uuid4().hex[:8]}@example.edu"
    response = client.post("/auth/register", json={"name": "Rae Set", "email": email, "password": password})
    assert response.status_code == 201, response.text
    return email


def _token_from(message: dict) -> str:
    match = re.search(r"reset-password\?token=([\w-]+)", message["text"])
    assert match, message["text"]
    return match.group(1)


def _login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_a_reset_link_sets_a_new_password_and_signs_in(client, outbox):
    email = _new_account(client)
    assert client.post("/auth/forgot-password", json={"email": email}).status_code == 200
    assert len(outbox) == 1 and outbox[0]["to"] == email

    response = client.post(
        "/auth/reset-password", json={"token": _token_from(outbox[0]), "password": "brand-new-pass"}
    )
    assert response.status_code == 200, response.text
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.json()["email"] == email

    assert _login(client, email, "original-pass").status_code == 401
    assert _login(client, email, "brand-new-pass").status_code == 200


def test_the_answer_does_not_reveal_whether_an_account_exists(client, outbox):
    email = _new_account(client)
    known = client.post("/auth/forgot-password", json={"email": email})
    unknown = client.post("/auth/forgot-password", json={"email": "nobody.here@example.edu"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert [m["to"] for m in outbox] == [email], "no email may go to an unknown address"


def test_email_case_and_spaces_do_not_matter(client, outbox):
    email = _new_account(client)
    client.post("/auth/forgot-password", json={"email": f"  {email.upper()} "})
    assert len(outbox) == 1 and outbox[0]["to"] == email


def test_a_link_works_only_once(client, outbox):
    email = _new_account(client)
    client.post("/auth/forgot-password", json={"email": email})
    token = _token_from(outbox[0])
    assert client.post("/auth/reset-password", json={"token": token, "password": "first-new-pass"}).status_code == 200
    again = client.post("/auth/reset-password", json={"token": token, "password": "second-new-pass"})
    assert again.status_code == 400
    assert _login(client, email, "first-new-pass").status_code == 200


def test_an_expired_link_is_refused(client, outbox):
    email = _new_account(client)
    client.post("/auth/forgot-password", json={"email": email})
    with SessionLocal() as db:
        for token in db.scalars(select(PasswordResetToken)):
            token.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    response = client.post(
        "/auth/reset-password", json={"token": _token_from(outbox[0]), "password": "too-late-pass"}
    )
    assert response.status_code == 400
    assert _login(client, email, "original-pass").status_code == 200


def test_asking_again_cancels_the_earlier_link(client, outbox):
    email = _new_account(client)
    client.post("/auth/forgot-password", json={"email": email})
    client.post("/auth/forgot-password", json={"email": email})
    first, second = _token_from(outbox[0]), _token_from(outbox[1])
    assert client.post("/auth/reset-password", json={"token": first, "password": "old-link-pass"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": second, "password": "new-link-pass"}).status_code == 200


def test_a_made_up_token_is_refused(client):
    response = client.post("/auth/reset-password", json={"token": "x" * 43, "password": "whatever-pass"})
    assert response.status_code == 400


def test_the_database_never_holds_the_raw_token(client, outbox):
    email = _new_account(client)
    client.post("/auth/forgot-password", json={"email": email})
    raw = _token_from(outbox[0])
    with SessionLocal() as db:
        stored = [t.token_hash for t in db.scalars(select(PasswordResetToken))]
    assert raw not in stored


def test_a_reset_signs_out_other_sessions(client, outbox):
    email = _new_account(client)
    old_session = _login(client, email, "original-pass").json()["access_token"]
    headers = {"Authorization": f"Bearer {old_session}"}
    assert client.get("/auth/me", headers=headers).status_code == 200

    client.post("/auth/forgot-password", json={"email": email})
    # Timestamps are whole seconds, so a token issued in the same second as the
    # reset still passes. Let the old session age past that second first.
    time.sleep(1.1)
    client.post("/auth/reset-password", json={"token": _token_from(outbox[0]), "password": "after-reset-pass"})

    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert "password was changed" in response.json()["detail"]


def test_the_link_points_at_the_configured_site(client, outbox, monkeypatch):
    monkeypatch.setattr(get_settings(), "site_url", "https://www.researchcoach.app/")
    email = _new_account(client)
    client.post("/auth/forgot-password", json={"email": email}, headers={"Host": "evil.example"})
    assert "https://www.researchcoach.app/reset-password?token=" in outbox[0]["text"]
    assert "evil.example" not in outbox[0]["text"]


def test_html_email_escapes_the_name(client, outbox):
    email = f"xss.{uuid.uuid4().hex[:6]}@example.edu"
    client.post("/auth/register", json={"name": "<script>alert(1)</script>", "email": email, "password": "password1"})
    client.post("/auth/forgot-password", json={"email": email})
    assert "<script>" not in outbox[0]["html"]


def test_requests_are_rate_limited(client, outbox, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_rate_limit", 2)
    email = _new_account(client)
    codes = [client.post("/auth/forgot-password", json={"email": email}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_without_an_email_key_nothing_is_sent_and_nothing_breaks(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_api_key", "")
    calls = []
    monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: calls.append(a))
    email = _new_account(client)
    assert client.post("/auth/forgot-password", json={"email": email}).status_code == 200
    assert calls == []


def test_site_url_falls_back_to_the_frontend_setting(monkeypatch):
    from app.core.config import Settings

    monkeypatch.delenv("SITE_URL", raising=False)
    monkeypatch.setenv("VITE_SITE_URL", "https://www.researchcoach.app")
    assert Settings(_env_file=None).site_url == "https://www.researchcoach.app"


def test_resend_receives_the_expected_request(monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test_key")
    captured = {}

    class Ok:
        status_code = 200
        text = "{}"

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json)
        return Ok()

    monkeypatch.setattr(email_service.httpx, "post", fake_post)
    assert email_service.send_email(to="a@example.edu", subject="S", text="T", html="<p>H</p>")
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test_key"
    assert captured["json"]["to"] == ["a@example.edu"]
    assert captured["json"]["from"] == get_settings().email_from


def test_a_provider_error_is_logged_not_raised(monkeypatch):
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test_key")

    class Rejected:
        status_code = 403
        text = "domain not verified"

    monkeypatch.setattr(email_service.httpx, "post", lambda *a, **k: Rejected())
    assert email_service.send_email(to="a@example.edu", subject="S", text="T", html="H") is False
