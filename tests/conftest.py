"""Keep the suite on the no-key path even if the shell has vendor credentials."""

from __future__ import annotations

import pytest

_VENDOR_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "LLAMA_CLOUD_API_KEY",
    "LLAMA_PARSE_TIER",
    "LLAMA_PARSE_TIMEOUT_S",
    "LLAMA_CLOUD_BASE_URL",
    "DOCVAL_CONTRACT_MAX_GAP_DAYS",
    "DOCVAL_ADDRESS_MAX_AGE_DAYS",
    "DOCVAL_GOLDEN_ROOT",
)


@pytest.fixture(autouse=True)
def _strip_vendor_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _VENDOR_ENV:
        monkeypatch.delenv(name, raising=False)
