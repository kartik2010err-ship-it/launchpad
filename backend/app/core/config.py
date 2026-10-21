import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-secret-not-for-production"
DEFAULT_SQLITE = "sqlite:///./research_coach.db"


class Settings(BaseSettings):
    """Runtime configuration. Every value is overridable by environment variable."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Research Coach"
    # "development" or "production". Left empty, it is inferred from the host:
    # a Vercel production deployment counts as production, everything else not.
    environment: str = ""
    database_url: str = DEFAULT_SQLITE
    secret_key: str = DEV_SECRET
    access_token_ttl_minutes: int = 60 * 24 * 7

    # Create the demo accounts (password coach1234) when the database is empty.
    # The sign-in page advertises them, so this stays on unless switched off.
    seed_demo_data: bool = True

    ai_provider: str = "heuristic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_base_url: str = "https://api.anthropic.com/v1/messages"
    # Kept under the hosting platform's function timeout, so a slow model call
    # falls back to the heuristic answer instead of being killed mid-request.
    anthropic_timeout_seconds: float = 45.0

    # Only needed when the frontend is served from a different origin than the
    # API. On Vercel both share one origin under /api and CORS never applies.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Attempts allowed per client per window on sign-in, sign-up and join codes.
    auth_rate_limit: int = 10
    auth_rate_window_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_serverless(self) -> bool:
        return bool(os.environ.get("VERCEL"))

    @property
    def is_production(self) -> bool:
        if self.environment:
            return self.environment.lower() == "production"
        return os.environ.get("VERCEL_ENV") == "production"

    @property
    def version(self) -> str:
        return (os.environ.get("VERCEL_GIT_COMMIT_SHA") or "local")[:7]

    @property
    def sqlalchemy_url(self) -> str:
        """``database_url`` with the driver SQLAlchemy needs spelled out.

        Hosted Postgres providers hand out ``postgres://`` or ``postgresql://``
        URLs. SQLAlchemy reads the bare form as psycopg2, which is not
        installed, so both are pointed at psycopg 3 here instead of asking
        whoever deploys to edit the string by hand.

        On serverless hosting the project directory is read-only, so the
        default SQLite file is moved to ``/tmp``. That keeps preview
        deployments working on throwaway demo data; production refuses SQLite
        entirely (see ``config_problems``).
        """

        url = self.database_url.strip()
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        if url == DEFAULT_SQLITE and self.is_serverless:
            return "sqlite:////tmp/research_coach.db"
        return url

    def config_problems(self) -> list[str]:
        """Settings that make a production deployment unsafe to serve.

        A default secret lets anyone mint a valid sign-in token for any
        account, and SQLite on serverless hosting lives in a temporary
        directory, so every account would vanish on the next cold start.
        """

        if not self.is_production:
            return []
        problems = []
        if self.secret_key == DEV_SECRET or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be set to a random value of at least 32 characters.")
        if self.sqlalchemy_url.startswith("sqlite"):
            problems.append("DATABASE_URL must point at a hosted Postgres database.")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
