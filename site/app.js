import { DOC_TYPES, parseIsoDate, reviewTexts } from "./engine.js";

const STRINGS = {
  es: {
    skip: "Saltar a la revisión",
    h1: "Revisar el expediente",
    lede: "Alta de personal sintética de Talento Bajio SA de CV: el navegador extrae los campos y aplica las cinco reglas.",
    caseLabel: "Expediente",
    ageLabel: "Antigüedad máxima del comprobante, días",
    gapLabel: "Holgura del inicio de contrato, días",
    run: "Revisar este expediente",
    restore: "Restaurar el texto",
    upload: "Subir .txt",
    record: "Datos del alta",
    name: "Nombre",
    hire: "Fecha de alta",
    start: "Inicio pactado",
    address: "Domicilio en el alta",
    addressHint: "La regla no compara esta calle. Solo usa la fecha del comprobante.",
    folio: "Folio",
    json: "JSON de esta revisión",
    "doc-identificacion": "Resumen de identificación",
    "doc-constancia_fiscal": "Constancia de situación fiscal",
    "doc-comprobante_domicilio": "Comprobante de domicilio",
    "doc-contrato": "Contrato laboral o carta oferta",
    rulesTitle: "Qué mira cada regla",
    reasonNote: "El motivo de cada regla sale del motor, en inglés, igual que el JSON del CLI.",
    "rule-name": "El nombre del alta coincide con la identificación, la constancia, el comprobante y el contrato. Acentos, el orden apellido nombre y una inicial siguen coincidiendo. Un apellido extra en un solo lado no coincide.",
    "rule-rfc": "El RFC del alta, la identificación, la constancia y el contrato está presente y es idéntico al quitar espacios y puntuación.",
    "rule-curp": "La CURP del alta, la identificación y la constancia coincide. Si el contrato imprime CURP, también tiene que coincidir. Si no la imprime, la regla no la exige.",
    "rule-address": "El comprobante está fechado el día del alta o antes, y no supera la ventana (90 días en la medición). Una fecha futura falla.",
    "rule-contract": "El inicio del contrato cae dentro de la holgura respecto al inicio pactado (7 días en la medición; el día del límite pasa). La firma existe y no es posterior al inicio. Sin fecha de firma, falla.",
    measureTitle: "Medición del extractor sobre los PDF",
    ruleCaption: "Reglas. La clase positiva es un fallo.",
    fieldCaption: "Campos extraídos contra el texto impreso.",
    colRule: "Regla",
    colFail: "Fallos",
    colPass: "Pases",
    colPrecision: "Precisión",
    colRecall: "Recall",
    colAccuracy: "Exactitud",
    colDoc: "Documento",
    colSlots: "Campos",
    colExact: "Coincidencia exacta",
    flowTitle: "Recorrido de un expediente",
    flow1: "Cuatro textos y el alta (application.json).",
    flow2: "Extractor determinista, las dos plantillas del generador.",
    flow3: "Cinco reglas sobre nombre, RFC, CURP, fecha del comprobante y fechas del contrato.",
    flow4: "Pasa o falla, con un motivo por regla.",
    flowNote: "En el CLI, el paso 2 puede ser pdfplumber, LlamaParse u OpenAI. Esta página solo corre el extractor determinista sobre texto.",
    limitsTitle: "Límites",
    lim1: "El extractor determinista solo entiende las dos plantillas del generador. Otra redacción deja el campo vacío y la regla que lo necesita falla.",
    lim2: "Esta página no abre PDF. El comando python -m docval run sí los abre con pdfplumber.",
    lim3: "LlamaParse y OpenAI no se llaman desde aquí. No hay backend ni llaves en el navegador.",
    lim4: "RFC y CURP son ficticios. Cada página del dataset trae la leyenda DOCUMENTO FICTICIO.",
    lim5: "No hay CFDI, estados de cuenta ni documentos de crédito en data/golden. El comprobante es un recibo de servicio ficticio y la constancia es de situación fiscal para el alta.",
    localTitle: "La misma revisión en la terminal",
    localBody: "Ese comando lee los PDF del expediente. EXP-0004 falla solo en name_consistency: la identificación dice Mariana Hernández Cruz y el alta dice Diego Vargas Ortiz.",
    colophon: "Atkinson Hyperlegible, porque un RFC y una CURP se leen carácter por carácter y esta fuente separa 0, O, I y l. El verde #1C4E3A es el único acento: tinta de sello sobre un expediente, plana. MIT, Edgar Flores, 2026.",
    pass: "PASA",
    fail: "FALLA",
    allPassed: "las 5 pasan",
    clean: "sin defecto etiquetado",
    customOption: "Texto propio",
    loading: "Cargando los 24 expedientes de data/golden.",
    loadError: "No se pudo leer data/site.json.",
    badWindow: "La ventana tiene que ser un entero de 0 en adelante.",
    badDate: "La fecha de alta y el inicio pactado usan la forma AAAA-MM-DD.",
    elapsed: "Revisión de texto en este navegador",
    match: "Pase, falla y motivo coinciden con labels.json de este expediente.",
    mismatch: "No coincide con labels.json. El motor del navegador se separó del archivo exportado.",
    edited: "El texto ya no es el del expediente. La etiqueta del dataset no aplica.",
    custom: "Texto propio. Si falta un campo, la regla que lo necesita falla.",
    windowNote: "La etiqueta se calculó con 90 días y 7 días. Otra ventana no se compara con labels.json.",
    injected: "Defecto inyectado en el generador",
    noneInjected: "El generador no inyectó defecto. Las reglas igual pueden exigir un límite justo.",
    uploadOk: "Se sustituyó el texto de",
    uploadNone: "Ningún archivo coincidió con identificacion, constancia, comprobante o contrato.",
    notRead: "sin texto",
    ms: "ms",
    sourceLead: "Fuente",
    disagreements: "desacuerdos con labels.json",
    timingLead: "Tiempo del proceso que abrió los PDF",
    timingMean: "media",
    timingMedian: "mediana",
    timingP95: "percentil 95",
    timingMax: "máximo",
    timingTotal: "Los 24 expedientes tardaron",
    timingNote: "Ese tiempo incluye abrir el PDF. Esta página no abre PDF: usa el .txt que está junto a cada uno.",
    allFields: "todos los campos",
    filesWord: "expedientes",
  },
  en: {
    skip: "Skip to the review",
    h1: "Review the file",
    lede: "Synthetic employee onboarding for Talento Bajio SA de CV: the browser extracts the fields and runs the five rules.",
    caseLabel: "File",
    ageLabel: "Maximum age of the proof of address, days",
    gapLabel: "Allowed gap for the contract start, days",
    run: "Review this file",
    restore: "Restore the text",
    upload: "Upload .txt",
    record: "Hire record",
    name: "Name",
    hire: "Hire date",
    start: "Agreed start",
    address: "Address on the hire record",
    addressHint: "The rule does not compare this street. It only uses the proof of address date.",
    folio: "File id",
    json: "JSON for this review",
    "doc-identificacion": "Identification summary",
    "doc-constancia_fiscal": "Tax status certificate",
    "doc-comprobante_domicilio": "Proof of address",
    "doc-contrato": "Employment contract or offer letter",
    rulesTitle: "What each rule checks",
    reasonNote: "Each reason is the engine's English sentence, the same text the CLI writes into JSON.",
    "rule-name": "The hire record name agrees with the identification summary, tax certificate, proof of address, and contract. Accents, surname first order, and a single initial still agree. An extra surname on only one side does not.",
    "rule-rfc": "The RFC on the hire record, identification summary, tax certificate, and contract is present and identical once spaces and punctuation are removed.",
    "rule-curp": "The CURP on the hire record, identification summary, and tax certificate agrees. A CURP printed on the contract must agree too. A contract with no CURP does not fail this rule.",
    "rule-address": "The proof of address is dated on the hire date or earlier, inside the window (90 days in the published measurement). A future date fails.",
    "rule-contract": "The contract start falls within the allowed gap of the agreed start (7 days in the measurement; a gap equal to the limit passes). A signature date is present and is not after the start. A missing signature fails.",
    measureTitle: "Extractor measurement on the PDFs",
    ruleCaption: "Rules. The positive class is a fail.",
    fieldCaption: "Extracted fields against the printed text.",
    colRule: "Rule",
    colFail: "Fails",
    colPass: "Passes",
    colPrecision: "Precision",
    colRecall: "Recall",
    colAccuracy: "Accuracy",
    colDoc: "Document",
    colSlots: "Slots",
    colExact: "Exact match",
    flowTitle: "Path of one file",
    flow1: "Four texts and the hire record (application.json).",
    flow2: "Deterministic extractor, the two layouts the generator prints.",
    flow3: "Five rules on name, RFC, CURP, proof of address date, and contract dates.",
    flow4: "Pass or fail, with a reason for each rule.",
    flowNote: "On the CLI, step 2 can be pdfplumber, LlamaParse, or OpenAI. This page runs only the deterministic extractor on text.",
    limitsTitle: "Limits",
    lim1: "The deterministic extractor only understands the two layouts the generator prints. Other wording leaves the field empty and the rule that needs it fails.",
    lim2: "This page does not open PDFs. python -m docval run does, with pdfplumber.",
    lim3: "LlamaParse and OpenAI are not called from here. There is no backend and no key in the browser.",
    lim4: "RFC and CURP values are fictional. Every dataset page carries the banner DOCUMENTO FICTICIO.",
    lim5: "data/golden has no CFDI, bank statement, or credit document. The proof of address is a fictional utility receipt and the tax certificate is for the hire file.",
    localTitle: "The same review in the terminal",
    localBody: "That command reads the PDFs. EXP-0004 fails only name_consistency: the identification summary says Mariana Hernández Cruz and the hire record says Diego Vargas Ortiz.",
    colophon: "Atkinson Hyperlegible, because an RFC and a CURP are read character by character and this face keeps 0, O, I, and l apart. #1C4E3A is the only accent: flat stamp ink on a paper file. MIT, Edgar Flores, 2026.",
    pass: "PASS",
    fail: "FAIL",
    allPassed: "all 5 passed",
    filesWord: "files",
    clean: "no labeled defect",
    customOption: "Your own text",
    loading: "Loading the 24 files from data/golden.",
    loadError: "Could not read data/site.json.",
    badWindow: "Each window has to be an integer of 0 or more.",
    badDate: "Hire date and agreed start use YYYY-MM-DD.",
    elapsed: "Text review in this browser",
    match: "Pass, fail, and reason match this file's labels.json.",
    mismatch: "This does not match labels.json. The browser engine drifted from the exported file.",
    edited: "The text is no longer the committed file. The dataset label does not apply.",
    custom: "Your own text. A rule that needs a missing field fails closed.",
    windowNote: "The label was computed with 90 days and 7 days. A different window is not compared with labels.json.",
    injected: "Defect injected by the generator",
    noneInjected: "The generator injected no defect. The rules can still be sitting on a boundary.",
    uploadOk: "Replaced the text of",
    uploadNone: "No file name matched identificacion, constancia, comprobante, or contrato.",
    notRead: "no text",
    ms: "ms",
    sourceLead: "Source",
    disagreements: "disagreements with labels.json",
    timingLead: "Time for the process that opened the PDFs",
    timingMean: "mean",
    timingMedian: "median",
    timingP95: "95th percentile",
    timingMax: "max",
    timingTotal: "All 24 files took",
    timingNote: "That time includes opening the PDF. This page does not open PDFs: it uses the .txt saved next to each one.",
    allFields: "all fields",
  },
};

const NOTES = {
  es: {
    "The contract omits accents. This is not a defect.": "El contrato omite acentos. No es un defecto.",
    "Proof of address is exactly 90 days old and should pass.": "El comprobante tiene exactamente 90 días. Debe pasar.",
    "The identificacion name belongs to a different synthetic person.": "El nombre de la identificación es de otra persona sintética.",
    "The constancia_fiscal RFC differs by one character.": "El RFC de la constancia fiscal difiere en un carácter.",
    "The constancia_fiscal CURP differs by one character.": "La CURP de la constancia fiscal difiere en un carácter.",
    "Proof of address is 151 days old.": "El comprobante tiene 151 días.",
    "The identification summary prints surnames first. This is not a defect.": "La identificación imprime los apellidos primero. No es un defecto.",
    "The contract start is exactly at the allowed gap and should pass.": "El inicio del contrato cae justo en el límite. Debe pasar.",
    "The contract start date falls outside the allowed gap.": "La fecha de inicio del contrato queda fuera de la holgura.",
    "The contract omits the signature date, so the expediente is incomplete.": "El contrato no trae fecha de firma.",
    "Proof of address is dated after the hire date.": "El comprobante está fechado después del alta.",
    "The comprobante_domicilio name belongs to a different synthetic person.": "El nombre del comprobante es de otra persona sintética.",
    "Proof of address is 181 days old.": "El comprobante tiene 181 días.",
  },
};

const DEFECTS = {
  es: {
    name_mismatch: "nombre de otra persona",
    rfc_mismatch: "RFC distinto",
    curp_mismatch: "CURP distinta",
    stale_address: "comprobante viejo",
    contract_start: "inicio fuera de la holgura",
    missing_signature: "sin fecha de firma",
    future_address: "comprobante posterior al alta",
  },
  en: {
    name_mismatch: "someone else's name",
    rfc_mismatch: "different RFC",
    curp_mismatch: "different CURP",
    stale_address: "stale proof of address",
    contract_start: "contract start outside the gap",
    missing_signature: "missing signature date",
    future_address: "proof of address after the hire date",
  },
};

const DOC_READ = {
  es: {
    identificacion: "Identificación",
    constancia_fiscal: "Constancia",
    comprobante_domicilio: "Comprobante",
    contrato: "Contrato",
  },
  en: {
    identificacion: "Identification",
    constancia_fiscal: "Tax certificate",
    comprobante_domicilio: "Proof of address",
    contrato: "Contract",
  },
};

const RULE_ORDER = [
  "name_consistency",
  "rfc_consistency",
  "curp_consistency",
  "address_recency",
  "contract_dates",
];

const FIELD_ORDER = [
  "identificacion",
  "constancia_fiscal",
  "comprobante_domicilio",
  "contrato",
];

let lang = "es";
let payload = null;
let activeId = "EXP-0004";
let baseline = "";
let lastReview = null;
let lastElapsed = 0;
let hydrating = false;
let counted = false;

function t(key) {
  return STRINGS[lang][key] ?? STRINGS.es[key] ?? key;
}

function failCount(count) {
  if (lang === "es") return count === 1 ? "1 regla falla" : `${count} reglas fallan`;
  return count === 1 ? "1 rule failed" : `${count} rules failed`;
}

function $(id) {
  return document.getElementById(id);
}

function applyStaticCopy() {
  document.documentElement.lang = lang;
  document.title = lang === "es" ? "Docval, revisión de expedientes" : "Docval, file review";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    if (key) node.textContent = t(key);
  });
  $("lang-es").setAttribute("aria-pressed", lang === "es" ? "true" : "false");
  $("lang-en").setAttribute("aria-pressed", lang === "en" ? "true" : "false");
  const group = document.querySelector(".lang");
  if (group) group.setAttribute("aria-label", lang === "es" ? "Idioma" : "Language");
}

function noteText(note) {
  if (lang === "es" && NOTES.es[note]) return NOTES.es[note];
  return note;
}

function defectText(id) {
  return DEFECTS[lang][id] || id;
}

function caseById(id) {
  return payload.cases.find((item) => item.case_id === id) || null;
}

function fillSelect() {
  const select = $("case");
  const current = select.value || activeId;
  select.replaceChildren();
  for (const item of payload.cases) {
    const option = document.createElement("option");
    option.value = item.case_id;
    const label = item.defects.length ? item.defects.map(defectText).join(", ") : t("clean");
    option.textContent = `${item.case_id} · ${label}`;
    select.append(option);
  }
  const custom = document.createElement("option");
  custom.value = "__custom__";
  custom.textContent = t("customOption");
  select.append(custom);
  select.value = [...select.options].some((option) => option.value === current) ? current : "EXP-0004";
}

function readApplication() {
  return {
    case_id: $("app-case").value,
    hire_date: $("app-hire").value.trim(),
    full_name: $("app-name").value,
    rfc: $("app-rfc").value,
    curp: $("app-curp").value,
    address: $("app-address").value,
    agreed_start: $("app-start").value.trim(),
  };
}

function readDocuments() {
  const documents = {};
  for (const docType of DOC_TYPES) {
    const value = $(`doc-${docType}`).value;
    if (value !== "") documents[docType] = value;
  }
  return documents;
}

function readWindows() {
  const age = $("age").value.trim();
  const gap = $("gap").value.trim();
  if (!/^\d+$/.test(age) || !/^\d+$/.test(gap)) return null;
  return { address_max_age_days: Number(age), contract_max_gap_days: Number(gap) };
}

function writeApplication(application) {
  $("app-case").value = application.case_id;
  $("app-hire").value = application.hire_date;
  $("app-name").value = application.full_name;
  $("app-rfc").value = application.rfc;
  $("app-curp").value = application.curp;
  $("app-address").value = application.address;
  $("app-start").value = application.agreed_start;
}

function writeDocuments(documents) {
  for (const docType of DOC_TYPES) {
    const node = $(`doc-${docType}`);
    node.value = documents[docType] ?? "";
    node.scrollTop = 0;
  }
  const docs = document.querySelector(".docs");
  if (docs) docs.scrollTop = 0;
}

function snapshot() {
  return JSON.stringify({
    application: readApplication(),
    documents: Object.fromEntries(DOC_TYPES.map((docType) => [docType, $(`doc-${docType}`).value])),
  });
}

function loadCase(id) {
  activeId = id;
  $("case").value = id;
  hydrating = true;
  if (id === "__custom__") {
    writeApplication({
      case_id: "TEXTO",
      hire_date: payload.source.as_of,
      full_name: "",
      rfc: "",
      curp: "",
      address: "",
      agreed_start: payload.source.as_of,
    });
    writeDocuments({});
    $("folio").textContent = "TEXTO";
    $("case-note").textContent = t("custom");
    baseline = "";
  } else {
    const item = caseById(id);
    writeApplication(item.application);
    writeDocuments(item.documents);
    $("folio").textContent = item.case_id;
    const defect = item.defects.length
      ? `${t("injected")}: ${item.defects.map(defectText).join(", ")}.`
      : t("noneInjected");
    const notes = item.notes.map(noteText).join(" ");
    $("case-note").textContent = notes ? `${defect} ${notes}` : defect;
    baseline = snapshot();
  }
  hydrating = false;
  review();
}

function clear(node) {
  node.replaceChildren();
}

function addReadout(list, label, parts) {
  const present = parts.filter((part) => part.value);
  if (!present.length) {
    const empty = document.createElement("li");
    empty.textContent = `${label}: ${t("notRead")}`;
    list.append(empty);
    return;
  }
  const li = document.createElement("li");
  const name = document.createElement("strong");
  name.textContent = label;
  li.append(name, document.createTextNode(": "));
  present.forEach((part, index) => {
    if (index) li.append(document.createTextNode(" · "));
    if (part.mono) {
      const code = document.createElement("span");
      code.className = "id";
      code.textContent = part.value;
      li.append(code);
    } else {
      li.append(document.createTextNode(part.value));
    }
  });
  list.append(li);
}

function renderReview() {
  const review = lastReview;
  if (!review) return;
  const failed = review.rules.filter((rule) => !rule.passed).length;
  const overall = $("overall");
  overall.textContent = review.overall_passed ? t("pass") : t("fail");
  overall.className = review.overall_passed ? "" : "fail";
  $("overall-count").textContent = failed ? failCount(failed) : t("allPassed");
  const elapsedText = lastElapsed < 10 ? lastElapsed.toFixed(2) : lastElapsed.toFixed(1);
  $("elapsed").textContent = `${t("elapsed")}: ${elapsedText} ${t("ms")}.`;

  const readout = $("readout");
  clear(readout);
  const extracted = review.extracted;
  const names = DOC_READ[lang];
  const ident = extracted.identificacion;
  addReadout(readout, names.identificacion, ident ? [
    { value: ident.full_name },
    { value: ident.rfc ? `RFC ${ident.rfc}` : "", mono: true },
    { value: ident.curp ? `CURP ${ident.curp}` : "", mono: true },
  ] : []);
  const fiscal = extracted.constancia_fiscal;
  addReadout(readout, names.constancia_fiscal, fiscal ? [
    { value: fiscal.holder_name },
    { value: fiscal.rfc ? `RFC ${fiscal.rfc}` : "", mono: true },
    { value: fiscal.tax_status },
    { value: fiscal.issue_date },
  ] : []);
  const proof = extracted.comprobante_domicilio;
  addReadout(readout, names.comprobante_domicilio, proof ? [
    { value: proof.holder_name },
    { value: proof.issuer },
    { value: proof.issue_date },
  ] : []);
  const contract = extracted.contrato;
  addReadout(readout, names.contrato, contract ? [
    { value: contract.employee_name },
    { value: contract.role },
    { value: contract.start_date ? `${lang === "es" ? "inicio" : "start"} ${contract.start_date}` : "" },
    { value: contract.signed_date ? `${lang === "es" ? "firma" : "signed"} ${contract.signed_date}` : "" },
  ] : []);

  const rules = $("rules");
  clear(rules);
  for (const rule of review.rules) {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "rule-head";
    const id = document.createElement("span");
    id.className = "id";
    id.textContent = rule.rule_id;
    const decision = document.createElement("span");
    decision.className = rule.passed ? "decision" : "decision fail";
    decision.textContent = rule.passed ? t("pass") : t("fail");
    head.append(id, decision);
    const reason = document.createElement("p");
    reason.className = "reason";
    reason.textContent = rule.reason;
    li.append(head, reason);
    rules.append(li);
  }

  const status = $("status");
  const windows = readWindows();
  const item = activeId === "__custom__" ? null : caseById(activeId);
  const defaultWindow = windows
    && windows.address_max_age_days === payload.policy.address_max_age_days
    && windows.contract_max_gap_days === payload.policy.contract_max_gap_days;
  if (!item) {
    status.textContent = t("custom");
  } else if (snapshot() !== baseline) {
    status.textContent = t("edited");
  } else if (!defaultWindow) {
    status.textContent = t("windowNote");
  } else {
    const same = JSON.stringify(review.rules) === JSON.stringify(item.expected.rules);
    status.textContent = same ? t("match") : t("mismatch");
  }

  const warnings = $("warnings");
  clear(warnings);
  for (const warning of review.warnings) {
    const li = document.createElement("li");
    li.textContent = warning;
    warnings.append(li);
  }
  $("json-out").textContent = JSON.stringify(
    {
      case_id: readApplication().case_id,
      overall_passed: review.overall_passed,
      elapsed_ms: Number(elapsedText),
      rules: review.rules,
      warnings: review.warnings,
      extracted: review.extracted,
    },
    null,
    2,
  );
}

function review() {
  const windows = readWindows();
  const application = readApplication();
  if (!windows) {
    $("status").textContent = t("badWindow");
    return;
  }
  if (!parseIsoDate(application.hire_date) || !parseIsoDate(application.agreed_start)) {
    $("status").textContent = t("badDate");
    return;
  }
  const started = performance.now();
  lastReview = reviewTexts(application, readDocuments(), windows);
  lastElapsed = performance.now() - started;
  $("folio").textContent = application.case_id.trim() || "…";
  renderReview();
}

function pct(value) {
  return `${(value * 100).toFixed(1)}%`;
}

function cell(text, numeric, count) {
  const td = document.createElement("td");
  if (numeric) td.className = "num";
  td.textContent = text;
  if (count != null) td.dataset.count = String(count);
  return td;
}

function renderEval() {
  const evalReport = payload.eval;
  const rulesBody = $("rule-metrics");
  clear(rulesBody);
  const ruleRows = [
    ...RULE_ORDER.map((id) => [id, evalReport.rules[id]]),
    ["overall", evalReport.overall],
  ];
  for (const [id, block] of ruleRows) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = id;
    name.className = "id";
    tr.append(
      name,
      cell(String(block.support_fail), true, block.support_fail),
      cell(String(block.support_pass), true, block.support_pass),
      cell(pct(block.precision), true),
      cell(pct(block.recall), true),
      cell(pct(block.accuracy), true),
    );
    rulesBody.append(tr);
  }

  const fieldsBody = $("field-metrics");
  clear(fieldsBody);
  const fieldRows = [
    ...FIELD_ORDER.map((id) => [id, evalReport.fields.by_document[id]]),
    ["all", {
      slots: evalReport.fields.slots,
      exact_matches: evalReport.fields.exact_matches,
      precision: evalReport.fields.precision,
      recall: evalReport.fields.recall,
    }],
  ];
  for (const [id, block] of fieldRows) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = id === "all" ? t("allFields") : id;
    if (id !== "all") name.className = "id";
    const exact = block.slots ? (block.exact_matches / block.slots) * 100 : 0;
    tr.append(
      name,
      cell(String(block.slots), true),
      cell(`${exact.toFixed(1)}%`, true),
      cell(pct(block.precision), true),
      cell(pct(block.recall), true),
    );
    fieldsBody.append(tr);
  }

  const timing = evalReport.timing;
  const seedWord = lang === "es" ? "semilla" : "seed";
  $("measure-source").textContent = `${t("sourceLead")}: ${payload.source.eval_report}. ${evalReport.parser_backend}, ${evalReport.extractor_backend}, ${evalReport.cases} ${t("filesWord")}, ${seedWord} ${evalReport.seed}. ${evalReport.disagreement_count} ${t("disagreements")}.`;
  $("timing").textContent = `${t("timingLead")}: ${t("timingMean")} ${timing.mean_ms} ${t("ms")}, ${t("timingMedian")} ${timing.p50_ms} ${t("ms")}, ${t("timingP95")} ${timing.p95_ms} ${t("ms")}, ${t("timingMax")} ${timing.max_ms} ${t("ms")}. ${t("timingTotal")} ${timing.total_ms} ${t("ms")}. ${t("timingNote")}`;

  if (!counted && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    counted = true;
    document.querySelectorAll("[data-count]").forEach((node) => {
      const target = Number(node.dataset.count);
      const start = performance.now();
      function frame(now) {
        const progress = Math.min(1, (now - start) / 600);
        const eased = 1 - (1 - progress) ** 3;
        node.textContent = String(Math.round(target * eased));
        if (progress < 1) requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    });
  }
}

function bind() {
  $("review").addEventListener("submit", (event) => {
    event.preventDefault();
    review();
    $("overall").focus();
  });
  $("case").addEventListener("change", () => loadCase($("case").value));
  $("restore").addEventListener("click", () => loadCase(activeId));
  for (const id of ["age", "gap", "app-name", "app-rfc", "app-curp", "app-address", "app-hire", "app-start", "app-case"]) {
    $(id).addEventListener("input", () => {
      if (!hydrating) review();
    });
  }
  for (const docType of DOC_TYPES) {
    $(`doc-${docType}`).addEventListener("input", () => {
      if (!hydrating) review();
    });
  }
  $("files").addEventListener("change", async (event) => {
    const input = event.target;
    const patterns = {
      identificacion: /identificacion/i,
      constancia_fiscal: /constancia/i,
      comprobante_domicilio: /comprobante|domicilio/i,
      contrato: /contrato|oferta/i,
    };
    const applied = [];
    for (const file of input.files || []) {
      const docType = DOC_TYPES.find((type) => patterns[type].test(file.name));
      if (!docType) continue;
      $(`doc-${docType}`).value = await file.text();
      applied.push(docType);
    }
    input.value = "";
    if (!applied.length) {
      $("status").textContent = t("uploadNone");
      return;
    }
    review();
    $("status").textContent = `${t("uploadOk")}: ${applied.join(", ")}. ${$("status").textContent}`;
  });
  $("lang-es").addEventListener("click", () => setLang("es"));
  $("lang-en").addEventListener("click", () => setLang("en"));
  $("overall").setAttribute("tabindex", "-1");
}

function setLang(next) {
  lang = next;
  try {
    localStorage.setItem("docval-lang", next);
  } catch {
    /* private mode */
  }
  applyStaticCopy();
  fillSelect();
  if (activeId !== "__custom__") {
    const item = caseById(activeId);
    if (item && snapshot() === baseline) {
      const defect = item.defects.length
        ? `${t("injected")}: ${item.defects.map(defectText).join(", ")}.`
        : t("noneInjected");
      const notes = item.notes.map(noteText).join(" ");
      $("case-note").textContent = notes ? `${defect} ${notes}` : defect;
    }
  } else {
    $("case-note").textContent = t("custom");
  }
  renderReview();
  renderEval();
}

async function init() {
  try {
    const stored = localStorage.getItem("docval-lang");
    if (stored === "en" || stored === "es") lang = stored;
  } catch {
    /* ignore */
  }
  applyStaticCopy();
  $("status").textContent = t("loading");
  try {
    const response = await fetch("data/site.json");
    if (!response.ok) throw new Error(String(response.status));
    payload = await response.json();
  } catch {
    $("status").textContent = t("loadError");
    return;
  }
  fillSelect();
  bind();
  loadCase("EXP-0004");
  renderEval();
}

init();
