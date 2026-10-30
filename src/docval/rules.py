"""Cross-document checks an onboarding reviewer runs on every expediente."""

from __future__ import annotations

from docval.config import Settings
from docval.schemas import Application, ExtractedFile, RuleResult
from docval.textutil import names_match, normalize_id

RULE_IDS: tuple[str, ...] = (
    "name_consistency",
    "rfc_consistency",
    "curp_consistency",
    "address_recency",
    "contract_dates",
)

RULE_DESCRIPTIONS: dict[str, str] = {
    "name_consistency": (
        "The hire-record name agrees with the identification summary, fiscal "
        "constancia, proof of address, and employment contract. Accents, "
        "surname-first order, and initials still agree."
    ),
    "rfc_consistency": (
        "The RFC on the hire record, identification summary, fiscal constancia, "
        "and contract is present and identical after removing spaces and punctuation."
    ),
    "curp_consistency": (
        "The CURP on the hire record, identification summary, and fiscal constancia "
        "agrees. A CURP printed on the contract must agree as well."
    ),
    "address_recency": (
        "The proof of address is dated on or before the hire date and is not older "
        "than the configured window (default 90 days)."
    ),
    "contract_dates": (
        "The contract start date is within the allowed gap of the agreed start "
        "(default 7 days; a gap equal to the limit still passes), and the contract "
        "has a signature date on or before that start date. A missing contract or "
        "a missing date fails the rule."
    ),
}


def _result(rule_id: str, passed: bool, reason: str) -> RuleResult:
    return RuleResult(rule_id=rule_id, passed=passed, reason=reason)


def _present(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def check_name_consistency(application: Application, extracted: ExtractedFile) -> RuleResult:
    ident = extracted.identificacion
    fiscal = extracted.constancia_fiscal
    proof = extracted.comprobante_domicilio
    contract = extracted.contrato
    pairs: list[tuple[str, str | None]] = [
        ("hire_record", application.full_name),
        ("identificacion", ident.full_name if ident else None),
        ("constancia_fiscal", fiscal.holder_name if fiscal else None),
        ("comprobante_domicilio", proof.holder_name if proof else None),
        ("contrato", contract.employee_name if contract else None),
    ]
    missing = [label for label, value in pairs if not _present(value)]
    if missing:
        return _result(
            "name_consistency",
            False,
            f"Missing name on: {', '.join(missing)}.",
        )
    mismatches: list[str] = []
    for label, value in pairs:
        if label == "hire_record" or value is None:
            continue
        if not names_match(application.full_name, value):
            mismatches.append(f"{label} '{value.strip()}'")
    if mismatches:
        return _result(
            "name_consistency",
            False,
            f"Name mismatch against hire record '{application.full_name}': "
            + "; ".join(mismatches)
            + ".",
        )
    return _result(
        "name_consistency",
        True,
        "Names agree across the hire record and all four documents.",
    )


def _compare_ids(
    rule_id: str,
    label: str,
    pairs: list[tuple[str, str | None]],
    *,
    optional: set[str] | None = None,
) -> RuleResult:
    optional = optional or set()
    normalized: list[tuple[str, str]] = []
    missing: list[str] = []
    for source, value in pairs:
        cleaned = normalize_id(value)
        if cleaned is None:
            if source not in optional:
                missing.append(source)
            continue
        normalized.append((source, cleaned))
    if missing:
        return _result(rule_id, False, f"Missing {label} on: {', '.join(missing)}.")
    distinct = {value for _, value in normalized}
    if len(distinct) > 1:
        rendered = ", ".join(f"{source} {value}" for source, value in normalized)
        return _result(rule_id, False, f"{label} mismatch: {rendered}.")
    return _result(rule_id, True, f"{label} agrees on {normalized[0][1]}.")


def check_rfc_consistency(application: Application, extracted: ExtractedFile) -> RuleResult:
    ident = extracted.identificacion
    fiscal = extracted.constancia_fiscal
    contract = extracted.contrato
    return _compare_ids(
        "rfc_consistency",
        "RFC",
        [
            ("hire_record", application.rfc),
            ("identificacion", ident.rfc if ident else None),
            ("constancia_fiscal", fiscal.rfc if fiscal else None),
            ("contrato", contract.rfc if contract else None),
        ],
    )


def check_curp_consistency(application: Application, extracted: ExtractedFile) -> RuleResult:
    ident = extracted.identificacion
    fiscal = extracted.constancia_fiscal
    contract = extracted.contrato
    return _compare_ids(
        "curp_consistency",
        "CURP",
        [
            ("hire_record", application.curp),
            ("identificacion", ident.curp if ident else None),
            ("constancia_fiscal", fiscal.curp if fiscal else None),
            ("contrato", contract.curp if contract else None),
        ],
        optional={"contrato"},
    )


def check_address_recency(
    application: Application,
    extracted: ExtractedFile,
    max_age_days: int,
) -> RuleResult:
    proof = extracted.comprobante_domicilio
    if proof is None or proof.issue_date is None:
        return _result("address_recency", False, "Proof of address has no issue date.")
    age = (application.hire_date - proof.issue_date).days
    issued = proof.issue_date.isoformat()
    hired = application.hire_date.isoformat()
    if age < 0:
        return _result(
            "address_recency",
            False,
            f"Proof of address issued {issued} is after the hire date {hired}.",
        )
    if age > max_age_days:
        return _result(
            "address_recency",
            False,
            f"Proof of address issued {issued} is {age} days before {hired} "
            f"(limit {max_age_days}).",
        )
    return _result(
        "address_recency",
        True,
        f"Proof of address issued {issued} is {age} days before the hire date "
        f"(limit {max_age_days}).",
    )


def check_contract_dates(
    application: Application,
    extracted: ExtractedFile,
    max_gap_days: int,
) -> RuleResult:
    problems: list[str] = []
    notes: list[str] = []
    contract = extracted.contrato
    agreed = application.agreed_start.isoformat()
    if contract is None or contract.start_date is None:
        problems.append("contract start date is missing")
    else:
        gap = abs((contract.start_date - application.agreed_start).days)
        started = contract.start_date.isoformat()
        if gap > max_gap_days:
            problems.append(
                f"contract start {started} vs agreed start {agreed} "
                f"({gap} days > limit {max_gap_days})"
            )
        else:
            notes.append(
                f"contract start {started} vs agreed start {agreed} "
                f"({gap} days <= limit {max_gap_days})"
            )
    if contract is None or contract.signed_date is None:
        problems.append("contract signature date is missing")
    elif contract.start_date is not None and contract.signed_date > contract.start_date:
        problems.append(
            f"contract signed {contract.signed_date.isoformat()} is after "
            f"the start date {contract.start_date.isoformat()}"
        )
    elif contract.start_date is not None:
        notes.append(
            f"contract signed {contract.signed_date.isoformat()} is on or before "
            f"the start date {contract.start_date.isoformat()}"
        )
    if problems:
        return _result("contract_dates", False, "; ".join(problems) + ".")
    return _result("contract_dates", True, "; ".join(notes) + ".")


def run_rules(
    application: Application,
    extracted: ExtractedFile,
    settings: Settings,
) -> list[RuleResult]:
    """Run every review rule. A file passes only when all rules pass."""
    return [
        check_name_consistency(application, extracted),
        check_rfc_consistency(application, extracted),
        check_curp_consistency(application, extracted),
        check_address_recency(application, extracted, settings.address_max_age_days),
        check_contract_dates(application, extracted, settings.contract_max_gap_days),
    ]
