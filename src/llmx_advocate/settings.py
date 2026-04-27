from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    llmx_default_provider: str = "openrouter"
    llmx_default_model: str = "deepseek/deepseek-chat"

    # Judge LLM is FIXED at the engine layer to keep QA semantics stable across
    # generation-side A/B tests. V0.1 uses DeepSeek V4 Flash — same family as v4-pro
    # (Chinese-strong, reasoning) but ~14× faster (~3.6s vs ~50s per call), which is
    # essential for the 5-judge-per-attempt × up-to-5-retries cost profile of P2.5.
    # Ling 2.6 1T:free was too strict on anti_relay_judge; v4-pro was accurate but
    # too slow per task. Switch to claude-opus-4-7 if/when an Anthropic key lands.
    llmx_judge_provider: str = "openrouter"
    llmx_judge_model: str = "deepseek/deepseek-v4-flash"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "llmx_advocate"
    postgres_user: str = "llmx"
    postgres_password: str = "change_me"

    # Override the constructed database URL (e.g. for local SQLite dev: sqlite+aiosqlite:///./dev.db).
    # When set, the postgres_* fields are ignored.
    llmx_database_url: str | None = None

    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "change_me"
    minio_bucket: str = "llmx-advocate"
    minio_secure: bool = False

    llmx_api_host: str = "0.0.0.0"
    llmx_api_port: int = 8000
    llmx_api_base_url: str = "http://localhost:8000"

    # Comma-separated list of allowed CORS origins. Vite dev server defaults to 5173.
    llmx_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # When set, terminal-status tasks (COMPLETED / FAILED) get their export
    # bundle written to this directory. The host's git-push cron then turns
    # that tree into a private GitHub repo. Empty/unset = persistence disabled
    # (default for tests + V0.1 CLI flow).
    llmx_outputs_dir: str = ""

    llmx_log_level: str = Field(default="INFO")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.llmx_cors_origins.split(",") if o.strip()]

    @property
    def outputs_dir_path(self) -> Path | None:
        return Path(self.llmx_outputs_dir).expanduser() if self.llmx_outputs_dir else None

    @property
    def database_url(self) -> str:
        if self.llmx_database_url:
            return self.llmx_database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        if self.llmx_database_url:
            return self.llmx_database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
