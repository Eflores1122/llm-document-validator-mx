"""Unit tests for normalization and the review rules."""

from datetime import date

from docval.config import Settings
from docval.rules import (
    check_address_recency,
    check_contract_dates,
    check_curp_consistency,
    check_name_consistency,
    check_rfc_consistency,
)
from docval.schemas import (
    Application,
    ComprobanteDomicilio,
    ConstanciaFiscal,
    Contrato,
    ExtractedFile,
    Identificacion,
)
from docval.textutil import names_match, normalize_id


def _application(**overrides: object) -> Application:
    payload: dict[str, object] = {
        "case_id": "EXP-0001",
        "hire_date": date(2026, 10, 1),
        "full_name": "María Fernanda Núñez García",
        "rfc": "NUGA900101AB1",
        "curp": "NUGA900101MJCZNR09",
        "address": "Av. Palma 128",
        "agreed_start": date(2026, 10, 1),
    }
    payload.update(overrides)
    return Application.model_validate(payload)


def _extracted() -> ExtractedFile:
    return ExtractedFile(
        identificacion=Identificacion(
            full_name="NUNEZ GARCIA, MARIA FERNANDA",
            rfc="NUGA900101AB1",
            curp="NUGA900101MJCZNR09",
        ),
        constancia_fiscal=ConstanciaFiscal(
            holder_name="Maria Fernanda Nunez Garcia",
            rfc="NUGA-900101-AB1",
            curp="NUGA900101MJCZNR09",
        ),
        comprobante_domicilio=ComprobanteDomicilio(
            holder_name="María F Núñez García",
            issue_date=date(2026, 7, 3),
        ),
        contrato=Contrato(
            employee_name="María Fernanda Núñez García",
            rfc="NUGA900101AB1",
            curp="NUGA900101MJCZNR09",
            signed_date=date(2026, 9, 28),
            start_date=date(2026, 10, 1),
        ),
    )


def test_names_match_accents_order_and_initials() -> None:
    assert names_match("María Fernanda Núñez García", "Maria Fernanda Nunez Garcia")
    assert names_match("Núñez García, María Fernanda", "María Fernanda Núñez García")
    assert names_match("María F Núñez García", "María Fernanda Núñez García")
    assert names_match("María del Carmen Ruiz", "Maria Carmen Ruiz")


def test_names_reject_a_different_person() -> None:
    assert not names_match("María Fernanda Núñez García", "Juan Carlos Pérez López")
    assert not names_match("Ana López", "Ana López Díaz")


def test_normalize_id_strips_punctuation() -> None:
    assert normalize_id("nuga-900101-ab1") == "NUGA900101AB1"
    assert normalize_id(None) is None


def test_clean_file_passes_every_rule() -> None:
    application = _application()
    extracted = _extracted()
    assert check_name_consistency(application, extracted).passed
    assert check_rfc_consistency(application, extracted).passed
    assert check_curp_consistency(application, extracted).passed
    assert check_address_recency(application, extracted, 90).passed
    assert check_contract_dates(application, extracted, 7).passed


def test_name_rfc_and_curp_mismatches_fail() -> None:
    application = _application()
    extracted = _extracted()
    assert extracted.identificacion is not None
    extracted.identificacion.full_name = "Diego Torres Vega"
    assert not check_name_consistency(application, extracted).passed
    extracted = _extracted()
    assert extracted.constancia_fiscal is not None
    extracted.constancia_fiscal.rfc = "NUGA900101ZZ9"
    assert not check_rfc_consistency(application, extracted).passed
    extracted = _extracted()
    assert extracted.constancia_fiscal is not None
    extracted.constancia_fiscal.curp = "NUGA900101MJCZNR00"
    assert not check_curp_consistency(application, extracted).passed


def test_contract_curp_is_optional_but_checked_when_present() -> None:
    application = _application()
    extracted = _extracted()
    assert extracted.contrato is not None
    extracted.contrato.curp = None
    assert check_curp_consistency(application, extracted).passed
    extracted.contrato.curp = "DIFFERENTCURP00000"
    assert not check_curp_consistency(application, extracted).passed


def test_address_window_boundaries() -> None:
    application = _application()
    extracted = _extracted()
    assert extracted.comprobante_domicilio is not None
    extracted.comprobante_domicilio.issue_date = date(2026, 7, 3)
    assert check_address_recency(application, extracted, 90).passed
    extracted.comprobante_domicilio.issue_date = date(2026, 7, 2)
    result = check_address_recency(application, extracted, 90)
    assert not result.passed
    assert "91 days" in result.reason
    extracted.comprobante_domicilio.issue_date = date(2026, 10, 6)
    assert not check_address_recency(application, extracted, 90).passed


def test_contract_dates_honor_the_gap_and_a_missing_signature() -> None:
    application = _application()
    extracted = _extracted()
    assert extracted.contrato is not None
    extracted.contrato.start_date = date(2026, 10, 8)
    extracted.contrato.signed_date = date(2026, 10, 5)
    assert check_contract_dates(application, extracted, 7).passed
    extracted.contrato.start_date = date(2026, 10, 9)
    result = check_contract_dates(application, extracted, 7)
    assert not result.passed
    assert "8 days" in result.reason
    extracted = _extracted()
    assert extracted.contrato is not None
    extracted.contrato.signed_date = None
    result = check_contract_dates(application, extracted, 7)
    assert not result.passed
    assert "signature date is missing" in result.reason
    extracted.contrato.signed_date = date(2026, 10, 4)
    extracted.contrato.start_date = date(2026, 10, 1)
    result = check_contract_dates(application, extracted, 7)
    assert not result.passed
    assert "after" in result.reason


def test_missing_fields_fail_closed() -> None:
    application = _application()
    extracted = _extracted()
    extracted.contrato = None
    assert not check_name_consistency(application, extracted).passed
    assert not check_contract_dates(application, extracted, 7).passed
    extracted = _extracted()
    extracted.comprobante_domicilio = None
    assert not check_address_recency(application, extracted, 90).passed


def test_settings_reject_a_negative_gap(monkeypatch) -> None:
    monkeypatch.setenv("DOCVAL_CONTRACT_MAX_GAP_DAYS", "-1")
    from docval.config import load_settings
    from docval.errors import DocvalError

    try:
        load_settings()
    except DocvalError as exc:
        assert "CONTRACT" in str(exc)
    else:
        raise AssertionError("expected DocvalError")


def test_default_settings_are_the_review_policy() -> None:
    settings = Settings()
    assert settings.contract_max_gap_days == 7
    assert settings.address_max_age_days == 90
    assert settings.openai_api_key is None
    assert settings.llama_cloud_api_key is None
