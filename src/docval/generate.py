"""Synthetic Mexican onboarding-file generator.

Every PDF and text file is fictional, watermarked, and built from a fixed seed.
RFC and CURP values are shaped like the public identifiers and are not issued
by SAT or RENAPO. Nothing here is a real person, employer, or document.
Talento Bajio SA de CV is a fictitious staffing company.
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from docval.config import Settings, load_settings
from docval.errors import DocvalError
from docval.rules import run_rules
from docval.schemas import (
    DOC_FILENAMES,
    Application,
    ComprobanteDomicilio,
    ConstanciaFiscal,
    Contrato,
    DocType,
    ExtractedFile,
    Identificacion,
    Labels,
    RuleExpectation,
)
from docval.textutil import strip_accents

DATASET_NAME = "docval-golden-mx-onboarding"
COMPANY = "Talento Bajio SA de CV"
HIRE_DATE = date(2026, 10, 1)
AGREED_START = date(2026, 10, 1)
FISCAL_ISSUE = date(2026, 9, 10)

# Defect cycle. Two passes of this list produce the published 24-case dataset.
CYCLE: tuple[tuple[str, ...], ...] = (
    (),
    (),
    (),
    ("name_mismatch",),
    ("rfc_mismatch",),
    ("curp_mismatch",),
    ("stale_address",),
    ("contract_start",),
    ("missing_signature",),
    ("future_address",),
    ("name_mismatch", "rfc_mismatch"),
    ("stale_address", "contract_start"),
)

NAME_TARGETS = ("contrato", "constancia_fiscal", "comprobante_domicilio", "identificacion")
RFC_TARGETS = ("identificacion", "constancia_fiscal", "contrato")
CURP_TARGETS = ("identificacion", "constancia_fiscal")

GIVEN: tuple[tuple[str, str], ...] = (
    ("María Fernanda", "M"),
    ("Juan Carlos", "H"),
    ("José Luis", "H"),
    ("Ana Sofía", "M"),
    ("Diego", "H"),
    ("Camila", "M"),
    ("Miguel Ángel", "H"),
    ("Valeria", "M"),
    ("Andrés", "H"),
    ("Renata", "M"),
    ("Fernando", "H"),
    ("Lucía", "M"),
    ("Alejandro", "H"),
    ("Daniela", "M"),
    ("Emilio", "H"),
    ("Regina", "M"),
    ("Ricardo", "H"),
    ("Paula", "M"),
    ("Héctor", "H"),
    ("Mariana", "M"),
)

SURNAMES: tuple[str, ...] = (
    "Pérez",
    "García",
    "Hernández",
    "Martínez",
    "López",
    "González",
    "Ramírez",
    "Sánchez",
    "Torres",
    "Rivera",
    "Gómez",
    "Díaz",
    "Cruz",
    "Morales",
    "Reyes",
    "Ortiz",
    "Vargas",
    "Castro",
    "Romero",
    "Núñez",
    "Domínguez",
    "Vega",
    "Rojas",
    "Silva",
    "Mendoza",
    "Guerrero",
    "Aguilar",
    "Vázquez",
    "Salazar",
    "Cortés",
)

CITIES: tuple[tuple[str, str, str, str], ...] = (
    ("Guadalajara", "Jalisco", "44100", "JC"),
    ("Monterrey", "Nuevo León", "64000", "NL"),
    ("Puebla", "Puebla", "72000", "PL"),
    ("Querétaro", "Querétaro", "76000", "QT"),
    ("Mérida", "Yucatán", "97000", "YN"),
    ("León", "Guanajuato", "37000", "GT"),
    ("Toluca", "Estado de México", "50000", "MC"),
    ("Oaxaca de Juárez", "Oaxaca", "68000", "OC"),
)

STREETS = (
    "Av. Palma 128",
    "Calle Gardenia 45",
    "Privada Cedro 12",
    "Blvd. Las Dunas 900",
    "Callejón del Arte 7",
    "Av. del Mezquite 250 Int. 2",
    "Calle Magnolia 33",
    "Cerrada Bugambilia 18",
)
NEIGHBORHOODS = (
    "Centro",
    "San Isidro",
    "Las Flores",
    "El Mirador",
    "La Paz",
    "Americana",
    "Los Encinos",
    "Reforma",
)
CLIENTS = (
    "Nube Clara SA de CV",
    "Taller Sol y Luna SA de CV",
    "Editorial Rio Lento SA de CV",
    "Logistica Bruma del Sur SA de CV",
    "Consultora Horizonte Ficticio SC",
    "Panaderia La Espiga Inventada SA de CV",
    "Estudios Marea Baja SC",
    "Transportes Cerro Azul SA de CV",
)
ROLES = (
    "Analista de reclutamiento",
    "Coordinacion de operaciones",
    "Especialista de capacitacion",
    "Auxiliar administrativo",
    "Enlace operativo",
    "Supervisor de sucursal",
    "Asistente de seleccion",
    "Generalista de personal",
)
ISSUERS = (
    "Luz del Valle Suministros SA de CV",
    "Agua Serena Servicios SA de CV",
    "Red Fibra Inventada SA de CV",
    "Gas de la Colina Ficticia SA de CV",
)
_HOMO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


@dataclass(frozen=True)
class Person:
    given: str
    paternal: str
    maternal: str
    birth_date: date
    sex: str
    rfc: str
    curp: str

    @property
    def full_name(self) -> str:
        return f"{self.given} {self.paternal} {self.maternal}"

    def formatted(self, style: str) -> str:
        if style == "inverted":
            return f"{self.paternal.upper()} {self.maternal.upper()}, {self.given.upper()}"
        if style == "accentless":
            return strip_accents(self.full_name)
        return self.full_name


@dataclass(frozen=True)
class Address:
    street: str
    neighborhood: str
    city: str
    state: str
    postal_code: str

    def one_line(self) -> str:
        return (
            f"{self.street}, {self.neighborhood}, {self.city}, {self.state}, "
            f"C.P. {self.postal_code}"
        )


@dataclass(frozen=True)
class CasePlan:
    defects: tuple[str, ...]
    address_age_days: int
    contract_mode: str
    name_styles: dict[str, str]
    variant: int
    name_target: str
    rfc_target: str
    curp_target: str


@dataclass
class BuiltCase:
    application: Application
    labels: Labels
    texts: dict[DocType, str]


def plan_for_index(index: int) -> CasePlan:
    """Deterministic defect plan. Index 0 is the first case."""
    slot = index % len(CYCLE)
    defects = CYCLE[slot]
    address_age = 20 + (index % 5) * 10
    contract_mode = "exact"
    if "stale_address" in defects:
        address_age = 91 + (index % 4) * 30
    if "future_address" in defects:
        address_age = -5
    if "contract_start" in defects:
        contract_mode = "late_start"
    elif "missing_signature" in defects:
        contract_mode = "missing_signature"
    elif slot == 1:
        address_age = 90
    elif slot == 2:
        contract_mode = "boundary"
    styles: dict[str, str] = {}
    if slot == 0:
        styles["identificacion"] = "inverted"
    elif slot == 1:
        styles["contrato"] = "accentless"
    return CasePlan(
        defects=defects,
        address_age_days=address_age,
        contract_mode=contract_mode,
        name_styles=styles,
        variant=(index // 2) % 2,
        name_target=NAME_TARGETS[index % len(NAME_TARGETS)],
        rfc_target=RFC_TARGETS[index % len(RFC_TARGETS)],
        curp_target=CURP_TARGETS[index % len(CURP_TARGETS)],
    )


def _letters(value: str) -> str:
    return "".join(char for char in strip_accents(value).upper() if char.isalpha())


def _rfc_prefix(given: str, paternal: str, maternal: str) -> str:
    paternal_letters = _letters(paternal)
    maternal_letters = _letters(maternal)
    given_letters = _letters(given.split()[0])
    first = paternal_letters[0] if paternal_letters else "X"
    vowel = next((char for char in paternal_letters[1:] if char in "AEIOU"), "X")
    third = maternal_letters[0] if maternal_letters else "X"
    fourth = given_letters[0] if given_letters else "X"
    return f"{first}{vowel}{third}{fourth}"


def _internal_consonant(value: str) -> str:
    letters = _letters(value)
    for char in letters[1:]:
        if char not in "AEIOU":
            return char
    return "X"


def _make_rfc(given: str, paternal: str, maternal: str, birth: date, rng: random.Random) -> str:
    """RFC-shaped synthetic id. The homoclave is random, not the SAT algorithm."""
    homo = "".join(rng.choice(_HOMO) for _ in range(3))
    return f"{_rfc_prefix(given, paternal, maternal)}{birth:%y%m%d}{homo}"


def _make_curp(
    given: str,
    paternal: str,
    maternal: str,
    birth: date,
    sex: str,
    state_code: str,
    rng: random.Random,
) -> str:
    """CURP-shaped synthetic id. The check digit is a toy sum, not RENAPO's."""
    consonants = (
        _internal_consonant(paternal)
        + _internal_consonant(maternal)
        + _internal_consonant(given.split()[0])
    )
    body = (
        f"{_rfc_prefix(given, paternal, maternal)}{birth:%y%m%d}{sex}{state_code}"
        f"{consonants}{rng.randint(0, 9)}"
    )
    check = sum(ord(char) for char in body) % 10
    curp = f"{body}{check}"
    if len(curp) != 18:
        raise DocvalError("internal error: synthetic CURP was not 18 characters")
    return curp


def _pick_person(rng: random.Random, state_code: str) -> Person:
    for _ in range(30):
        given, sex = rng.choice(GIVEN)
        paternal = rng.choice(SURNAMES)
        maternal = rng.choice(SURNAMES)
        if paternal == maternal:
            continue
        birth = date(rng.randint(1972, 1998), rng.randint(1, 12), rng.randint(1, 28))
        return Person(
            given=given,
            paternal=paternal,
            maternal=maternal,
            birth_date=birth,
            sex=sex,
            rfc=_make_rfc(given, paternal, maternal, birth, rng),
            curp=_make_curp(given, paternal, maternal, birth, sex, state_code, rng),
        )
    raise DocvalError("could not build a synthetic person")


def _mutate_id(value: str, rng: random.Random) -> str:
    chars = list(value)
    index = len(chars) - 1 - rng.randrange(3)
    current = chars[index]
    replacement = rng.choice([char for char in _HOMO if char != current])
    chars[index] = replacement
    mutated = "".join(chars)
    if mutated == value:
        raise DocvalError("internal error: identifier mutation made no change")
    return mutated


def _banner(case_id: str) -> list[str]:
    return [
        "DOCUMENTO FICTICIO - SIN VALIDEZ OFICIAL",
        "SYNTHETIC FIXTURE - NOT A REAL DOCUMENT",
        f"{COMPANY} - expediente de alta de personal",
        f"Folio de demostracion: {case_id}",
        "",
    ]


def _footer() -> list[str]:
    return [
        "",
        "Generado por docval como expediente sintetico.",
        "Documento ficticio. No es un archivo real de un trabajador.",
    ]


def _shown_id(value: str, variant: int) -> str:
    if variant == 0:
        return value
    return f"{value[:10]}-{value[10:]}"


def _render_identificacion(
    case_id: str,
    *,
    variant: int,
    name: str,
    birth_date: date,
    sex: str,
    rfc: str,
    curp: str,
    address: Address,
    voter_key: str,
) -> str:
    shown_rfc = _shown_id(rfc, variant)
    shown_curp = _shown_id(curp, variant)
    if variant == 0:
        body = [
            "RESUMEN DE IDENTIFICACION",
            "Este resumen es ficticio. No es una credencial oficial.",
            "No contiene fotografia, codigo de barras ni zona MRZ.",
            f"Nombre completo: {name}",
            f"Fecha de nacimiento: {birth_date.isoformat()}",
            f"Sexo: {sex}",
            f"CURP: {shown_curp}",
            f"RFC: {shown_rfc}",
            f"Domicilio: {address.one_line()}",
            f"Clave de elector ficticia: {voter_key}",
        ]
    else:
        body = [
            "CONSTANCIA DE IDENTIFICACION",
            "Documento ficticio con los datos de una identificacion. No es un INE.",
            f"Nombre: {name}",
            f"Nacimiento: {birth_date.isoformat()}",
            f"Sexo: {sex}",
            f"Clave CURP: {shown_curp}",
            f"R.F.C.: {shown_rfc}",
            f"Domicilio: {address.one_line()}",
            f"Clave de elector ficticia: {voter_key}",
        ]
    return "\n".join(_banner(case_id) + body + _footer()) + "\n"


def _render_constancia(
    case_id: str,
    *,
    variant: int,
    name: str,
    rfc: str,
    curp: str,
    postal_code: str,
    issue_date: date,
) -> str:
    shown_rfc = _shown_id(rfc, variant)
    shown_curp = _shown_id(curp, variant)
    if variant == 0:
        body = [
            "CONSTANCIA DE SITUACION FISCAL",
            "Documento ficticio. No fue emitido por una autoridad.",
            f"Nombre: {name}",
            f"RFC: {shown_rfc}",
            f"CURP: {shown_curp}",
            f"Codigo postal fiscal: {postal_code}",
            f"Fecha de emision: {issue_date.isoformat()}",
            "Estatus: Activo",
        ]
    else:
        body = [
            "CONSTANCIA DE SITUACION FISCAL",
            "Copia ficticia para un expediente de alta. Sin validez oficial.",
            f"Contribuyente: {name}",
            f"R.F.C.: {shown_rfc}",
            f"Clave CURP: {shown_curp}",
            f"C.P. fiscal: {postal_code}",
            f"Emitida: {issue_date.isoformat()}",
            "Situacion: Activo",
        ]
    return "\n".join(_banner(case_id) + body + _footer()) + "\n"


def _render_comprobante(
    case_id: str,
    *,
    variant: int,
    name: str,
    address: Address,
    issuer: str,
    issue_date: date,
    account: str,
) -> str:
    name_label = "Nombre" if variant == 0 else "Cliente"
    body = [
        "COMPROBANTE DE DOMICILIO",
        f"Emisor: {issuer}",
        f"Fecha de emision: {issue_date.isoformat()}",
        f"Cuenta de servicio: {account}",
        f"{name_label}: {name}",
        f"Calle: {address.street}",
        f"Colonia: {address.neighborhood}",
        f"Ciudad: {address.city}",
        f"Estado: {address.state}",
        f"Codigo postal: {address.postal_code}",
    ]
    return "\n".join(_banner(case_id) + body + _footer()) + "\n"


def _render_contrato(
    case_id: str,
    *,
    variant: int,
    name: str,
    rfc: str,
    curp: str,
    role: str,
    client: str,
    start: date,
    signed: date | None,
) -> str:
    shown_rfc = _shown_id(rfc, variant)
    shown_curp = _shown_id(curp, variant)
    signed_line = None if signed is None else f"Fecha de firma: {signed.isoformat()}"
    if variant == 0:
        body = [
            "CONTRATO LABORAL",
            f"Empleador: {COMPANY}",
            f"Trabajador: {name}",
            f"RFC: {shown_rfc}",
            f"CURP: {shown_curp}",
            f"Puesto: {role}",
            f"Cliente de asignacion: {client}",
            f"Fecha de inicio: {start.isoformat()}",
            "Tipo: Tiempo indeterminado",
        ]
    else:
        body = [
            "CARTA OFERTA",
            f"Empresa: {COMPANY}",
            f"Candidato: {name}",
            f"R.F.C.: {shown_rfc}",
            f"Clave CURP: {shown_curp}",
            f"Puesto ofrecido: {role}",
            f"Cliente de asignacion: {client}",
            f"Fecha de ingreso: {start.isoformat()}",
            "Documento: Carta oferta",
        ]
    if signed_line is not None:
        body.insert(-1, signed_line)
    return "\n".join(_banner(case_id) + body + _footer()) + "\n"


def _display(person: Person, doc: str, styles: dict[str, str]) -> str:
    return person.formatted(styles.get(doc, "canonical"))


def build_cases(n: int, seed: int, settings: Settings | None = None) -> list[BuiltCase]:
    """Build `n` labeled cases. The same seed always yields the same files."""
    if n < 1:
        raise DocvalError("cases must be at least 1")
    settings = settings or load_settings()
    rng = random.Random(seed)
    cases: list[BuiltCase] = []
    for index in range(n):
        cases.append(_build_one(index, rng, settings))
    return cases


def _contract_dates(mode: str, max_gap_days: int) -> tuple[date, date | None]:
    if mode == "boundary":
        start = AGREED_START + timedelta(days=max_gap_days)
    elif mode == "late_start":
        start = AGREED_START + timedelta(days=max_gap_days + 23)
    else:
        start = AGREED_START
    if mode == "missing_signature":
        return start, None
    return start, start - timedelta(days=3)


def _build_one(index: int, rng: random.Random, settings: Settings) -> BuiltCase:
    plan = plan_for_index(index)
    case_id = f"EXP-{index + 1:04d}"
    city, state, postal, state_code = CITIES[index % len(CITIES)]
    address = Address(
        street=STREETS[index % len(STREETS)],
        neighborhood=NEIGHBORHOODS[(index * 3) % len(NEIGHBORHOODS)],
        city=city,
        state=state,
        postal_code=postal,
    )
    applicant = _pick_person(rng, state_code)
    other = _pick_person(rng, state_code)
    while other.full_name == applicant.full_name or other.rfc == applicant.rfc:
        other = _pick_person(rng, state_code)

    people = {doc: applicant for doc in NAME_TARGETS}
    if "name_mismatch" in plan.defects:
        people[plan.name_target] = other

    id_docs = ("identificacion", "constancia_fiscal", "contrato")
    rfcs = {doc: applicant.rfc for doc in id_docs}
    curps = {doc: applicant.curp for doc in id_docs}
    if "rfc_mismatch" in plan.defects:
        rfcs[plan.rfc_target] = _mutate_id(applicant.rfc, rng)
    if "curp_mismatch" in plan.defects:
        curps[plan.curp_target] = _mutate_id(applicant.curp, rng)

    issue_date = HIRE_DATE - timedelta(days=plan.address_age_days)
    client = CLIENTS[index % len(CLIENTS)]
    role = ROLES[index % len(ROLES)]
    issuer = ISSUERS[index % len(ISSUERS)]
    voter_key = "SYN" + "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(15))
    account = f"SYN-{rng.randint(100000, 999999)}"
    start_date, signed_date = _contract_dates(plan.contract_mode, settings.contract_max_gap_days)
    contract_kind = "Tiempo indeterminado" if plan.variant == 0 else "Carta oferta"

    texts = {
        DocType.IDENTIFICACION: _render_identificacion(
            case_id,
            variant=plan.variant,
            name=_display(people["identificacion"], "identificacion", plan.name_styles),
            birth_date=applicant.birth_date,
            sex=applicant.sex,
            rfc=rfcs["identificacion"],
            curp=curps["identificacion"],
            address=address,
            voter_key=voter_key,
        ),
        DocType.CONSTANCIA_FISCAL: _render_constancia(
            case_id,
            variant=plan.variant,
            name=_display(people["constancia_fiscal"], "constancia_fiscal", plan.name_styles),
            rfc=rfcs["constancia_fiscal"],
            curp=curps["constancia_fiscal"],
            postal_code=address.postal_code,
            issue_date=FISCAL_ISSUE,
        ),
        DocType.COMPROBANTE_DOMICILIO: _render_comprobante(
            case_id,
            variant=plan.variant,
            name=_display(
                people["comprobante_domicilio"], "comprobante_domicilio", plan.name_styles
            ),
            address=address,
            issuer=issuer,
            issue_date=issue_date,
            account=account,
        ),
        DocType.CONTRATO: _render_contrato(
            case_id,
            variant=plan.variant,
            name=_display(people["contrato"], "contrato", plan.name_styles),
            rfc=rfcs["contrato"],
            curp=curps["contrato"],
            role=role,
            client=client,
            start=start_date,
            signed=signed_date,
        ),
    }
    application = Application(
        case_id=case_id,
        hire_date=HIRE_DATE,
        full_name=applicant.full_name,
        rfc=applicant.rfc,
        curp=applicant.curp,
        address=address.one_line(),
        agreed_start=AGREED_START,
    )
    truth = ExtractedFile(
        identificacion=Identificacion(
            full_name=people["identificacion"].full_name,
            rfc=rfcs["identificacion"],
            curp=curps["identificacion"],
            birth_date=applicant.birth_date,
            address=address.one_line(),
            sex=applicant.sex,
        ),
        constancia_fiscal=ConstanciaFiscal(
            holder_name=people["constancia_fiscal"].full_name,
            rfc=rfcs["constancia_fiscal"],
            curp=curps["constancia_fiscal"],
            postal_code=address.postal_code,
            issue_date=FISCAL_ISSUE,
            tax_status="Activo",
        ),
        comprobante_domicilio=ComprobanteDomicilio(
            holder_name=people["comprobante_domicilio"].full_name,
            street=address.street,
            neighborhood=address.neighborhood,
            city=address.city,
            state=address.state,
            postal_code=address.postal_code,
            issue_date=issue_date,
            issuer=issuer,
        ),
        contrato=Contrato(
            employee_name=people["contrato"].full_name,
            rfc=rfcs["contrato"],
            curp=curps["contrato"],
            employer=COMPANY,
            role=role,
            signed_date=signed_date,
            start_date=start_date,
            contract_kind=contract_kind,
        ),
    )
    expected = {
        result.rule_id: RuleExpectation(passed=result.passed, reason=result.reason)
        for result in run_rules(application, truth, settings)
    }
    labels = Labels(
        case_id=case_id,
        defects=list(plan.defects),
        notes=_notes(plan),
        truth=truth,
        expected_rules=expected,
    )
    return BuiltCase(application=application, labels=labels, texts=texts)


def _notes(plan: CasePlan) -> list[str]:
    notes: list[str] = []
    if "name_mismatch" in plan.defects:
        notes.append(f"The {plan.name_target} name belongs to a different synthetic person.")
    if "rfc_mismatch" in plan.defects:
        notes.append(f"The {plan.rfc_target} RFC differs by one character.")
    if "curp_mismatch" in plan.defects:
        notes.append(f"The {plan.curp_target} CURP differs by one character.")
    if "stale_address" in plan.defects:
        notes.append(f"Proof of address is {plan.address_age_days} days old.")
    if "future_address" in plan.defects:
        notes.append("Proof of address is dated after the hire date.")
    if "contract_start" in plan.defects:
        notes.append("The contract start date falls outside the allowed gap.")
    if "missing_signature" in plan.defects:
        notes.append("The contract omits the signature date, so the expediente is incomplete.")
    if plan.name_styles.get("identificacion") == "inverted":
        notes.append("The identification summary prints surnames first. This is not a defect.")
    if plan.name_styles.get("contrato") == "accentless":
        notes.append("The contract omits accents. This is not a defect.")
    if plan.contract_mode == "boundary":
        notes.append("The contract start is exactly at the allowed gap and should pass.")
    if plan.address_age_days == 90 and "stale_address" not in plan.defects:
        notes.append("Proof of address is exactly 90 days old and should pass.")
    if not notes:
        notes.append("Clean file. Every review rule should pass.")
    return notes


def write_pdf(path: Path, text: str) -> None:
    """Write a one-column text PDF. `invariant=1` keeps the bytes seed-stable."""
    canvas = Canvas(str(path), pagesize=letter, invariant=1)
    canvas.setTitle("Documento ficticio - Talento Bajio")
    canvas.setAuthor("docval synthetic generator")
    canvas.setSubject("Fictitious onboarding fixture. Not a real document.")
    _width, height = letter
    y = height - 54
    canvas.setFont("Helvetica", 10)
    for line in text.splitlines():
        if y < 54:
            canvas.showPage()
            canvas.setFont("Helvetica", 10)
            y = height - 54
        canvas.drawString(48, y, line)
        y -= 14
    canvas.save()


def write_dataset(
    out: Path,
    *,
    cases: int = 24,
    seed: int = 42,
    settings: Settings | None = None,
    force: bool = False,
) -> dict[str, object]:
    """Write a golden dataset of PDFs, sidecar text, hire records, and labels."""
    _prepare_output(out, force)
    built = build_cases(cases, seed, settings)
    cases_root = out / "cases"
    for case in built:
        folder = cases_root / case.application.case_id
        folder.mkdir(parents=True)
        _write_json(folder / "application.json", case.application.model_dump(mode="json"))
        _write_json(folder / "labels.json", case.labels.model_dump(mode="json"))
        for doc_type, text in case.texts.items():
            pdf_path = folder / DOC_FILENAMES[doc_type]
            pdf_path.with_suffix(".txt").write_text(text, encoding="utf-8")
            write_pdf(pdf_path, text)
    manifest: dict[str, object] = {
        "name": DATASET_NAME,
        "version": 1,
        "seed": seed,
        "case_count": cases,
        "as_of": HIRE_DATE.isoformat(),
        "company": COMPANY,
        "description": (
            "Fully synthetic Mexican employee-onboarding files for demos and evaluation. "
            "Not real people, employers, or documents. Talento Bajio SA de CV is fictitious."
        ),
        "cases": [case.application.case_id for case in built],
    }
    _write_json(out / "manifest.json", manifest)
    return manifest


def _prepare_output(out: Path, force: bool) -> None:
    if out.exists():
        if not force:
            raise DocvalError(f"{out} already exists; pass --force to replace it")
        if out.is_symlink() or not out.is_dir():
            raise DocvalError(f"{out} is not a directory; refusing to replace it")
        occupied = any(out.iterdir())
        looks_like_dataset = (out / "manifest.json").is_file() or (out / "cases").is_dir()
        if occupied and not looks_like_dataset:
            raise DocvalError(f"{out} is not a docval dataset; refusing to delete it")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
