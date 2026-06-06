"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Central settings object. Reads from the process environment / .env."""

    def __init__(self) -> None:
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@db:5432/monitoring",
        )
        # SQLAlchemy needs the +psycopg2 driver; tolerate a plain postgres URL.
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+psycopg2://", 1
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+psycopg2://", 1
            )

        self.db_sslmode: str = os.getenv("DB_SSLMODE", "require")
        self.cors_origins: list[str] = _split_csv(
            os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        )
        self.auto_init_db: bool = os.getenv("AUTO_INIT_DB", "true").lower() == "true"

        # Anomaly detection tuning
        self.zscore_window: int = int(os.getenv("ZSCORE_WINDOW", "50"))
        self.zscore_warning: float = float(os.getenv("ZSCORE_WARNING", "3.0"))
        self.zscore_critical: float = float(os.getenv("ZSCORE_CRITICAL", "4.5"))

    @property
    def connect_args(self) -> dict:
        """psycopg2 connect args. Cloud Supabase requires SSL."""
        if self.db_sslmode and "supabase" in self.database_url:
            return {"sslmode": self.db_sslmode}
        if self.db_sslmode in {"require", "verify-full", "verify-ca"}:
            return {"sslmode": self.db_sslmode}
        return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
