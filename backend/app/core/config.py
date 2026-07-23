"""Application configuration.

Every setting is read here and nowhere else — no scattered os.getenv calls
(see .claude/rules/security.md).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root, next to docker-compose.yml. Resolved absolutely
# because the backend runs from backend/ while alembic, pytest, and scripts all
# run from different directories — a relative "./.env" silently finds nothing
# and every setting falls back to its default.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Database ---------------------------------------------------------
    database_url: str = (
        "postgresql+psycopg2://pmpilot:pmpilot_dev@localhost:5433/pmpilot"
    )

    # Used ONLY to execute NL2SQL-generated queries. This is a required
    # defence layer, not an optimisation — never point NL2SQL at database_url.
    database_url_readonly: str = (
        "postgresql+psycopg2://pmpilot_ro:pmpilot_ro_dev@localhost:5433/pmpilot"
    )

    # --- LLM --------------------------------------------------------------
    anthropic_api_key: str = ""

    # Pinned for the whole project. Changing this mid-project makes the grounded
    # and naive experiment arms incomparable — see .claude/rules/experiment.md.
    anthropic_model_id: str = "claude-opus-4-8"
    anthropic_effort: str = "high"

    # --- App --------------------------------------------------------------
    app_name: str = "PMPilot"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
