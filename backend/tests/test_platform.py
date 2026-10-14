"""Hosting concerns: configuration, the serverless entry point, health, rate
limits and email handling. None of this is research logic, all of it decides
whether a student can sign in at all."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import DEV_SECRET, Settings, get_settings
from app.db.bootstrap import _stored_fingerprint, prepare_database, schema_fingerprint
from app.main import app
from app.seed import run as seed_run

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def seeded() -> None:
    seed_run()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    from sqlalchemy import delete

    from app.db.session import SessionLocal
    from app.models.security import RateLimitHit

    with SessionLocal() as db:
        db.execute(delete(RateLimitHit))
        db.commit()


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "given",
    [
        "postgres://u:p@host/db?sslmode=require",
        "postgresql://u:p@host/db?sslmode=require",
        "postgresql+psycopg://u:p@host/db?sslmode=require",
    ],
)
def test_hosted_postgres_urls_use_the_installed_driver(given):
    assert Settings(database_url=given).sqlalchemy_url == "postgresql+psycopg://u:p@host/db?sslmode=require"


def test_default_sqlite_moves_to_tmp_on_serverless(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings(_env_file=None).sqlalchemy_url == "sqlite:////tmp/research_coach.db"


def test_production_refuses_a_default_secret_and_sqlite(monkeypatch):
    monkeypatch.setenv("VERCEL_ENV", "production")
    problems = Settings(
        environment="", secret_key=DEV_SECRET, database_url="sqlite:///./x.db"
    ).config_problems()
    assert any("SECRET_KEY" in p for p in problems)
    assert any("DATABASE_URL" in p for p in problems)


def test_production_with_real_settings_has_no_problems():
    settings = Settings(
        environment="production",
        secret_key="x" * 40,
        database_url="postgresql://u:p@host/db",
    )
    assert settings.config_problems() == []


def test_a_preview_deployment_is_not_production(monkeypatch):
    monkeypatch.setenv("VERCEL_ENV", "preview")
    assert Settings(environment="").config_problems() == []


def test_misconfigured_production_serves_503_not_forgeable_tokens(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", DEV_SECRET)
    response = client.post("/auth/login", json={"email": "ava@example.edu", "password": "coach1234"})
    assert response.status_code == 503
    health = client.get("/health")
    assert health.status_code == 503
    assert health.json()["config_problems"]


def test_root_and_backend_requirements_match():
    def packages(path: Path) -> set[str]:
        return {
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith(("#", "-r"))
        }

    assert packages(ROOT / "requirements.txt") == packages(ROOT / "backend" / "requirements.txt")


# --------------------------------------------------------------------------- #
# Serverless entry point
# --------------------------------------------------------------------------- #


@pytest.fixture()
def vercel_client() -> TestClient:
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return TestClient(module.app)


def test_api_prefix_is_stripped_for_the_backend(vercel_client):
    assert vercel_client.get("/api/health").status_code == 200
    login = vercel_client.post(
        "/api/auth/login", json={"email": "ava@example.edu", "password": "coach1234"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    me = vercel_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "ava@example.edu"


def test_a_rewrite_destination_path_is_mapped_back(vercel_client):
    """Should Vercel ever deliver the rewrite target, the original route wins."""

    response = vercel_client.get("/api/index?path=competitions/azsef&x=1")
    assert response.status_code == 200, response.text
    assert response.json()["key"] == "azsef"


def test_interactive_docs_resolve_under_the_prefix(vercel_client):
    docs = vercel_client.get("/api/docs")
    assert docs.status_code == 200
    assert "/api/openapi.json" in docs.text


# --------------------------------------------------------------------------- #
# Health, errors, bootstrap
# --------------------------------------------------------------------------- #


def test_health_checks_the_database(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_responses_carry_a_request_id(client):
    assert client.get("/competitions").headers.get("X-Request-Id")


def test_an_unhandled_error_returns_json_with_a_reference(monkeypatch):
    from app.api.routes import planning

    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(planning, "list_competitions", boom, raising=False)
    route = next(r for r in app.routes if getattr(r, "path", "") == "/competitions")
    monkeypatch.setattr(route, "endpoint", boom)
    monkeypatch.setattr(route.dependant, "call", boom)
    response = TestClient(app, raise_server_exceptions=False).get("/competitions")
    assert response.status_code == 500
    assert "Reference:" in response.json()["detail"]


def test_bootstrap_records_the_schema_and_skips_on_the_next_cold_start(monkeypatch):
    prepare_database(force=True)
    assert _stored_fingerprint() == schema_fingerprint()

    from app.db import bootstrap

    def must_not_run(*_a, **_k):
        raise AssertionError("an unchanged schema should not be re-synced")

    monkeypatch.setattr(bootstrap, "sync_columns", must_not_run)
    prepare_database()  # unchanged models: one query, no sync


# --------------------------------------------------------------------------- #
# Email handling and rate limits
# --------------------------------------------------------------------------- #


def test_sign_in_ignores_email_case(client):
    response = client.post("/auth/login", json={"email": " Ava@Example.EDU", "password": "coach1234"})
    assert response.status_code == 200, response.text


def test_registering_the_same_email_in_another_case_conflicts(client):
    email = f"case.{uuid.uuid4().hex[:6]}@example.edu"
    first = client.post("/auth/register", json={"name": "A", "email": email, "password": "password1"})
    assert first.status_code == 201
    second = client.post(
        "/auth/register", json={"name": "B", "email": email.upper(), "password": "password1"}
    )
    assert second.status_code == 409


def test_repeated_failed_sign_ins_are_throttled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_rate_limit", 3)
    bad = {"email": "noah@example.edu", "password": "wrong-password"}
    codes = [client.post("/auth/login", json=bad).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]
    # The right password is refused too while the account is locked out.
    good = client.post("/auth/login", json={"email": "noah@example.edu", "password": "coach1234"})
    assert good.status_code == 429


def test_successful_sign_ins_are_not_counted(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_rate_limit", 2)
    good = {"email": "priya@example.edu", "password": "coach1234"}
    assert all(client.post("/auth/login", json=good).status_code == 200 for _ in range(5))


def test_join_code_guessing_is_throttled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_rate_limit", 2)
    token = client.post(
        "/auth/login", json={"email": "riley@example.edu", "password": "coach1234"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    codes = [
        client.post("/workspaces/join", json={"join_code": f"NOPE-{i}"}, headers=headers).status_code
        for i in range(3)
    ]
    assert codes == [404, 404, 429]


def test_a_shared_classroom_address_gets_a_larger_budget(client, monkeypatch):
    """Thirty students behind one school IP must be able to sign up together."""

    monkeypatch.setattr(get_settings(), "auth_rate_limit", 2)
    stamp = uuid.uuid4().hex[:6]
    codes = [
        client.post(
            "/auth/register",
            json={"name": f"S{i}", "email": f"s{i}.{stamp}@example.edu", "password": "password1"},
        ).status_code
        for i in range(10)
    ]
    assert codes == [201] * 10
