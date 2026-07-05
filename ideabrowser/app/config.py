"""Application configuration, sourced from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    app_name: str = "IdeaBrowser Reimagined"
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "IDEABROWSER_DATABASE_URL", "sqlite:///./ideabrowser.db"
        )
    )
    # AI provider: "anthropic" when an API key is configured, otherwise the
    # deterministic offline engine (keeps every feature usable without a key).
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    anthropic_model: str = field(
        default_factory=lambda: os.environ.get("IDEABROWSER_MODEL", "claude-opus-4-8")
    )
    # Payments: "mock" ships with the repo; a Stripe adapter plugs in behind
    # the same PaymentGateway interface.
    payment_provider: str = field(
        default_factory=lambda: os.environ.get("IDEABROWSER_PAYMENTS", "mock")
    )

    @property
    def ai_backend(self) -> str:
        return "anthropic" if self.anthropic_api_key else "deterministic"


settings = Settings()
