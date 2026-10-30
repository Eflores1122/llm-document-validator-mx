"""Runtime settings loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from docval.errors import DocvalError


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True)
class Settings:
    """Thresholds and optional vendor credentials.

    Empty API keys select the local parser and the deterministic extractor.
    """

    contract_max_gap_days: int = 7
    address_max_age_days: int = 90
    openai_model: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    llama_cloud_api_key: str | None = None
    llama_parse_tier: str = "fast"
    llama_parse_timeout_s: float = 120.0
    llama_cloud_base_url: str = "https://api.cloud.llamaindex.ai"

    def validate(self) -> Settings:
        if self.contract_max_gap_days < 0:
            raise DocvalError("DOCVAL_CONTRACT_MAX_GAP_DAYS must be >= 0")
        if self.address_max_age_days < 0:
            raise DocvalError("DOCVAL_ADDRESS_MAX_AGE_DAYS must be >= 0")
        if self.llama_parse_timeout_s <= 0:
            raise DocvalError("LLAMA_PARSE_TIMEOUT_S must be positive")
        return self


def load_settings() -> Settings:
    """Read settings from the environment. Blank vendor keys count as unset."""
    gap_raw = os.environ.get("DOCVAL_CONTRACT_MAX_GAP_DAYS", "7")
    age_raw = os.environ.get("DOCVAL_ADDRESS_MAX_AGE_DAYS", "90")
    timeout_raw = os.environ.get("LLAMA_PARSE_TIMEOUT_S", "120")
    try:
        max_gap = int(gap_raw)
        max_age = int(age_raw)
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise DocvalError("numeric settings must be valid numbers") from exc
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    tier = os.environ.get("LLAMA_PARSE_TIER", "fast").strip() or "fast"
    base = os.environ.get("LLAMA_CLOUD_BASE_URL", "https://api.cloud.llamaindex.ai").strip()
    return Settings(
        contract_max_gap_days=max_gap,
        address_max_age_days=max_age,
        openai_model=model,
        openai_api_key=_blank(os.environ.get("OPENAI_API_KEY")),
        llama_cloud_api_key=_blank(os.environ.get("LLAMA_CLOUD_API_KEY")),
        llama_parse_tier=tier,
        llama_parse_timeout_s=timeout,
        llama_cloud_base_url=base.rstrip("/"),
    ).validate()
