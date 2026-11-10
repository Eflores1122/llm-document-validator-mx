// Browser port of the deterministic extractor and the five review rules.
// Source of truth: src/docval/textutil.py, extractors.py, rules.py, pipeline.py.
// site/check-engine.mjs compares this file with Python on the golden cases.

const PARTICLES = new Set(["DE", "DEL", "LA", "LAS", "LOS", "Y"]);

const DOC_ORDER = [
  "identificacion",
  "constancia_fiscal",
  "comprobante_domicilio",
  "contrato",
];

const ID_LABELS = ["RFC", "R.F.C.", "R.F.C"];
const CURP_LABELS = ["CURP", "Clave CURP"];

export function stripAccents(value) {
  return value.normalize("NFD").replace(/\p{M}/gu, "");
}

export function nameTokens(value) {
  let cleaned = stripAccents(value).toUpperCase().replace(/,/g, " ");
  cleaned = cleaned.replace(/[^A-Z\s]/g, " ");
  cleaned = cleaned.replace(/\s+/g, " ").trim();
  if (!cleaned) return [];
  return cleaned.split(" ").filter((token) => token && !PARTICLES.has(token));
}

function sequenceChars(value) {
  return Array.from(value);
}

function chainB(chars, autojunk) {
  const b2j = new Map();
  chars.forEach((elt, index) => {
    const indices = b2j.get(elt);
    if (indices) indices.push(index);
    else b2j.set(elt, [index]);
  });
  const bjunk = new Set();
  const popular = new Set();
  const n = chars.length;
  if (autojunk && n >= 200) {
    const ntest = Math.floor(n / 100) + 1;
    for (const [elt, idxs] of b2j) {
      if (idxs.length > ntest) popular.add(elt);
    }
    for (const elt of popular) b2j.delete(elt);
  }
  return { b2j, bjunk };
}

function findLongestMatch(a, b, b2j, bjunk, alo, ahi, blo, bhi) {
  let besti = alo;
  let bestj = blo;
  let bestsize = 0;
  let j2len = new Map();
  for (let i = alo; i < ahi; i += 1) {
    const newj2len = new Map();
    const indices = b2j.get(a[i]) || [];
    for (const j of indices) {
      if (j < blo) continue;
      if (j >= bhi) break;
      const k = (j2len.get(j - 1) || 0) + 1;
      newj2len.set(j, k);
      if (k > bestsize) {
        besti = i - k + 1;
        bestj = j - k + 1;
        bestsize = k;
      }
    }
    j2len = newj2len;
  }
  while (
    besti > alo &&
    bestj > blo &&
    !bjunk.has(b[bestj - 1]) &&
    a[besti - 1] === b[bestj - 1]
  ) {
    besti -= 1;
    bestj -= 1;
    bestsize += 1;
  }
  while (
    besti + bestsize < ahi &&
    bestj + bestsize < bhi &&
    !bjunk.has(b[bestj + bestsize]) &&
    a[besti + bestsize] === b[bestj + bestsize]
  ) {
    bestsize += 1;
  }
  while (
    besti > alo &&
    bestj > blo &&
    bjunk.has(b[bestj - 1]) &&
    a[besti - 1] === b[bestj - 1]
  ) {
    besti -= 1;
    bestj -= 1;
    bestsize += 1;
  }
  while (
    besti + bestsize < ahi &&
    bestj + bestsize < bhi &&
    bjunk.has(b[bestj + bestsize]) &&
    a[besti + bestsize] === b[bestj + bestsize]
  ) {
    bestsize += 1;
  }
  return [besti, bestj, bestsize];
}

function matchingBlocks(a, b, autojunk) {
  const { b2j, bjunk } = chainB(b, autojunk);
  const queue = [[0, a.length, 0, b.length]];
  const blocks = [];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = findLongestMatch(a, b, b2j, bjunk, alo, ahi, blo, bhi);
    if (k) {
      blocks.push([i, j, k]);
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  blocks.sort((left, right) => left[0] - right[0] || left[1] - right[1] || left[2] - right[2]);
  let i1 = 0;
  let j1 = 0;
  let k1 = 0;
  const collapsed = [];
  for (const [i2, j2, k2] of blocks) {
    if (i1 + k1 === i2 && j1 + k1 === j2) {
      k1 += k2;
    } else {
      if (k1) collapsed.push([i1, j1, k1]);
      i1 = i2;
      j1 = j2;
      k1 = k2;
    }
  }
  if (k1) collapsed.push([i1, j1, k1]);
  let matches = 0;
  for (const block of collapsed) matches += block[2];
  return matches;
}

export function sequenceRatio(left, right) {
  const a = sequenceChars(left);
  const b = sequenceChars(right);
  const length = a.length + b.length;
  if (!length) return 1;
  return (2 * matchingBlocks(a, b, true)) / length;
}

function compatible(left, right) {
  if (left === right) return true;
  if (left.length === 1 && right.startsWith(left)) return true;
  if (right.length === 1 && left.startsWith(right)) return true;
  if (left.length >= 5 && right.length >= 5) return sequenceRatio(left, right) >= 0.92;
  return false;
}

function covers(source, target) {
  const used = target.map(() => false);
  for (const token of source) {
    let found = false;
    for (let index = 0; index < target.length; index += 1) {
      if (used[index]) continue;
      if (compatible(token, target[index])) {
        used[index] = true;
        found = true;
        break;
      }
    }
    if (!found) return false;
  }
  return true;
}

export function namesMatch(left, right) {
  if (left == null || right == null) return false;
  const leftTokens = nameTokens(String(left));
  const rightTokens = nameTokens(String(right));
  if (!leftTokens.length || !rightTokens.length) return false;
  return covers(leftTokens, rightTokens) && covers(rightTokens, leftTokens);
}

export function normalizeId(value) {
  if (value == null) return null;
  const cleaned = String(value).replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  return cleaned || null;
}

export function parseIsoDate(value) {
  if (value == null) return null;
  const match = /(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const utc = new Date(Date.UTC(year, month - 1, day));
  if (utc.getUTCFullYear() !== year || utc.getUTCMonth() !== month - 1 || utc.getUTCDate() !== day) {
    return null;
  }
  return { year, month, day, iso: `${match[1]}-${match[2]}-${match[3]}` };
}

function daysBetween(later, earlier) {
  const left = Date.UTC(later.year, later.month - 1, later.day);
  const right = Date.UTC(earlier.year, earlier.month - 1, earlier.day);
  return Math.round((left - right) / 86400000);
}

function findLabeled(text, labels) {
  for (const label of labels) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(`^\\s*${escaped}\\s*:\\s*(.+?)\\s*$`, "imu");
    const match = pattern.exec(text);
    if (match) return match[1].trim();
  }
  return null;
}

function blankExtracted() {
  return {
    identificacion: null,
    constancia_fiscal: null,
    comprobante_domicilio: null,
    contrato: null,
  };
}

function extractIdentificacion(text) {
  return {
    full_name: findLabeled(text, ["Nombre completo", "Nombre"]),
    rfc: normalizeId(findLabeled(text, ID_LABELS)),
    curp: normalizeId(findLabeled(text, CURP_LABELS)),
    birth_date: dateOrNull(findLabeled(text, ["Fecha de nacimiento", "Nacimiento"])),
    address: findLabeled(text, ["Domicilio"]),
    sex: findLabeled(text, ["Sexo"]),
  };
}

function extractConstancia(text) {
  const issued = findLabeled(text, ["Fecha de emision", "Fecha de emisión", "Emitida"]);
  return {
    holder_name: findLabeled(text, ["Nombre", "Contribuyente"]),
    rfc: normalizeId(findLabeled(text, ID_LABELS)),
    curp: normalizeId(findLabeled(text, CURP_LABELS)),
    postal_code: findLabeled(text, ["Codigo postal fiscal", "C.P. fiscal"]),
    issue_date: dateOrNull(issued),
    tax_status: findLabeled(text, ["Estatus", "Situacion", "Situación"]),
  };
}

function extractComprobante(text) {
  const issued = findLabeled(text, ["Fecha de emision", "Fecha de emisión"]);
  return {
    holder_name: findLabeled(text, ["Nombre", "Cliente"]),
    street: findLabeled(text, ["Calle"]),
    neighborhood: findLabeled(text, ["Colonia"]),
    city: findLabeled(text, ["Ciudad"]),
    state: findLabeled(text, ["Estado"]),
    postal_code: findLabeled(text, ["Codigo postal", "Código postal", "C.P."]),
    issue_date: dateOrNull(issued),
    issuer: findLabeled(text, ["Emisor"]),
  };
}

function extractContrato(text) {
  return {
    employee_name: findLabeled(text, ["Trabajador", "Candidato"]),
    rfc: normalizeId(findLabeled(text, ID_LABELS)),
    curp: normalizeId(findLabeled(text, CURP_LABELS)),
    employer: findLabeled(text, ["Empleador", "Empresa"]),
    role: findLabeled(text, ["Puesto", "Puesto ofrecido"]),
    signed_date: dateOrNull(findLabeled(text, ["Fecha de firma"])),
    start_date: dateOrNull(findLabeled(text, ["Fecha de inicio", "Fecha de ingreso"])),
    contract_kind: findLabeled(text, ["Tipo", "Documento"]),
  };
}

function dateOrNull(value) {
  const parsed = parseIsoDate(value);
  return parsed ? parsed.iso : null;
}

export function extractDocument(docType, text) {
  if (docType === "identificacion") return extractIdentificacion(text);
  if (docType === "constancia_fiscal") return extractConstancia(text);
  if (docType === "comprobante_domicilio") return extractComprobante(text);
  if (docType === "contrato") return extractContrato(text);
  throw new Error(`unsupported document type ${docType}`);
}

function present(value) {
  return value != null && String(value).trim() !== "";
}

function result(ruleId, passed, reason) {
  return { rule_id: ruleId, passed, reason };
}

function asDate(value) {
  if (value == null || value === "") return null;
  if (typeof value === "object" && value.iso) return value;
  return parseIsoDate(value);
}

export function checkNameConsistency(application, extracted) {
  const ident = extracted.identificacion;
  const fiscal = extracted.constancia_fiscal;
  const proof = extracted.comprobante_domicilio;
  const contract = extracted.contrato;
  const pairs = [
    ["hire_record", application.full_name],
    ["identificacion", ident ? ident.full_name : null],
    ["constancia_fiscal", fiscal ? fiscal.holder_name : null],
    ["comprobante_domicilio", proof ? proof.holder_name : null],
    ["contrato", contract ? contract.employee_name : null],
  ];
  const missing = pairs.filter(([, value]) => !present(value)).map(([label]) => label);
  if (missing.length) {
    return result("name_consistency", false, `Missing name on: ${missing.join(", ")}.`);
  }
  const mismatches = [];
  for (const [label, value] of pairs) {
    if (label === "hire_record" || value == null) continue;
    if (!namesMatch(application.full_name, value)) mismatches.push(`${label} '${String(value).trim()}'`);
  }
  if (mismatches.length) {
    return result(
      "name_consistency",
      false,
      `Name mismatch against hire record '${application.full_name}': ${mismatches.join("; ")}.`,
    );
  }
  return result(
    "name_consistency",
    true,
    "Names agree across the hire record and all four documents.",
  );
}

function compareIds(ruleId, label, pairs, optional) {
  const skip = optional || new Set();
  const normalized = [];
  const missing = [];
  for (const [source, value] of pairs) {
    const cleaned = normalizeId(value);
    if (cleaned == null) {
      if (!skip.has(source)) missing.push(source);
      continue;
    }
    normalized.push([source, cleaned]);
  }
  if (missing.length) {
    return result(ruleId, false, `Missing ${label} on: ${missing.join(", ")}.`);
  }
  const distinct = new Set(normalized.map(([, value]) => value));
  if (distinct.size > 1) {
    const rendered = normalized.map(([source, value]) => `${source} ${value}`).join(", ");
    return result(ruleId, false, `${label} mismatch: ${rendered}.`);
  }
  return result(ruleId, true, `${label} agrees on ${normalized[0][1]}.`);
}

export function checkRfcConsistency(application, extracted) {
  const ident = extracted.identificacion;
  const fiscal = extracted.constancia_fiscal;
  const contract = extracted.contrato;
  return compareIds("rfc_consistency", "RFC", [
    ["hire_record", application.rfc],
    ["identificacion", ident ? ident.rfc : null],
    ["constancia_fiscal", fiscal ? fiscal.rfc : null],
    ["contrato", contract ? contract.rfc : null],
  ]);
}

export function checkCurpConsistency(application, extracted) {
  const ident = extracted.identificacion;
  const fiscal = extracted.constancia_fiscal;
  const contract = extracted.contrato;
  return compareIds(
    "curp_consistency",
    "CURP",
    [
      ["hire_record", application.curp],
      ["identificacion", ident ? ident.curp : null],
      ["constancia_fiscal", fiscal ? fiscal.curp : null],
      ["contrato", contract ? contract.curp : null],
    ],
    new Set(["contrato"]),
  );
}

export function checkAddressRecency(application, extracted, maxAgeDays) {
  const proof = extracted.comprobante_domicilio;
  const issued = proof ? asDate(proof.issue_date) : null;
  if (!proof || !issued) {
    return result("address_recency", false, "Proof of address has no issue date.");
  }
  const hired = asDate(application.hire_date);
  const age = daysBetween(hired, issued);
  if (age < 0) {
    return result(
      "address_recency",
      false,
      `Proof of address issued ${issued.iso} is after the hire date ${hired.iso}.`,
    );
  }
  if (age > maxAgeDays) {
    return result(
      "address_recency",
      false,
      `Proof of address issued ${issued.iso} is ${age} days before ${hired.iso} (limit ${maxAgeDays}).`,
    );
  }
  return result(
    "address_recency",
    true,
    `Proof of address issued ${issued.iso} is ${age} days before the hire date (limit ${maxAgeDays}).`,
  );
}

export function checkContractDates(application, extracted, maxGapDays) {
  const problems = [];
  const notes = [];
  const contract = extracted.contrato;
  const agreed = asDate(application.agreed_start);
  const agreedIso = agreed ? agreed.iso : String(application.agreed_start);
  const start = contract ? asDate(contract.start_date) : null;
  if (!contract || !start) {
    problems.push("contract start date is missing");
  } else {
    const gap = Math.abs(daysBetween(start, agreed));
    if (gap > maxGapDays) {
      problems.push(
        `contract start ${start.iso} vs agreed start ${agreedIso} (${gap} days > limit ${maxGapDays})`,
      );
    } else {
      notes.push(
        `contract start ${start.iso} vs agreed start ${agreedIso} (${gap} days <= limit ${maxGapDays})`,
      );
    }
  }
  const signed = contract ? asDate(contract.signed_date) : null;
  if (!contract || !signed) {
    problems.push("contract signature date is missing");
  } else if (start && daysBetween(signed, start) > 0) {
    problems.push(`contract signed ${signed.iso} is after the start date ${start.iso}`);
  } else if (start) {
    notes.push(`contract signed ${signed.iso} is on or before the start date ${start.iso}`);
  }
  if (problems.length) return result("contract_dates", false, `${problems.join("; ")}.`);
  return result("contract_dates", true, `${notes.join("; ")}.`);
}

export function runRules(application, extracted, settings) {
  const age = settings.address_max_age_days;
  const gap = settings.contract_max_gap_days;
  return [
    checkNameConsistency(application, extracted),
    checkRfcConsistency(application, extracted),
    checkCurpConsistency(application, extracted),
    checkAddressRecency(application, extracted, age),
    checkContractDates(application, extracted, gap),
  ];
}

export function reviewTexts(application, documents, settings) {
  const warnings = [];
  const extracted = blankExtracted();
  const seen = new Set();
  const provided = documents || {};
  for (const docType of DOC_ORDER) {
    if (!Object.prototype.hasOwnProperty.call(provided, docType)) continue;
    const text = provided[docType];
    if (text == null) continue;
    seen.add(docType);
    const body = String(text);
    if (!body.includes("SIN VALIDEZ OFICIAL") && !body.includes("SYNTHETIC FIXTURE")) {
      warnings.push(`${docType} is missing the synthetic-fixture banner`);
    }
    if (!body.trim()) {
      warnings.push(`${docType}: ${docType} text is empty`);
      continue;
    }
    extracted[docType] = extractDocument(docType, body);
  }
  const missing = DOC_ORDER.filter((docType) => !seen.has(docType));
  if (missing.length) warnings.push(`missing documents: ${missing.join(", ")}`);
  const rules = runRules(application, extracted, settings);
  return {
    overall_passed: rules.every((rule) => rule.passed),
    rules,
    warnings,
    extracted,
  };
}

export const DOC_TYPES = DOC_ORDER;
