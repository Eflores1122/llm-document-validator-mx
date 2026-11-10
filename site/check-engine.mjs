// Compare site/engine.js with the Python results stored in site/data/site.json.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { namesMatch, reviewTexts, runRules, sequenceRatio } from "./engine.js";

const root = dirname(fileURLToPath(import.meta.url));
const payload = JSON.parse(readFileSync(join(root, "data", "site.json"), "utf8"));
const failures = [];

function note(message) {
  failures.push(message);
}

function same(actual, expected, label) {
  const left = JSON.stringify(actual);
  const right = JSON.stringify(expected);
  if (left !== right) note(`${label}\n  js: ${left}\n  py: ${right}`);
}

const policy = payload.policy;

for (const item of payload.cases) {
  const review = reviewTexts(item.application, item.documents, policy);
  same(review.overall_passed, item.expected.overall_passed, `${item.case_id} overall`);
  same(review.rules, item.expected.rules, `${item.case_id} rules`);
  same(review.warnings, item.expected.warnings, `${item.case_id} warnings`);
  same(review.extracted, item.expected.extracted, `${item.case_id} extracted`);
}

for (const item of payload.rule_fixtures) {
  const rules = runRules(item.application, item.extracted, {
    address_max_age_days: item.address_max_age_days,
    contract_max_gap_days: item.contract_max_gap_days,
  });
  same(rules, item.rules, `fixture ${item.name}`);
}

for (const item of payload.text_fixtures) {
  const review = reviewTexts(item.application, item.documents, {
    address_max_age_days: item.address_max_age_days,
    contract_max_gap_days: item.contract_max_gap_days,
  });
  same(
    {
      overall_passed: review.overall_passed,
      rules: review.rules,
      warnings: review.warnings,
      extracted: review.extracted,
    },
    item.expected,
    `text ${item.name}`,
  );
}

for (const item of payload.name_pairs) {
  const actual = namesMatch(item.left, item.right);
  if (actual !== item.match) note(`namesMatch(${item.left}, ${item.right}) js=${actual} py=${item.match}`);
}

for (const item of payload.ratios) {
  const actual = sequenceRatio(item.left, item.right);
  if (Math.abs(actual - item.ratio) > 1e-9) {
    note(`ratio(${item.left.slice(0, 24)}, ...) js=${actual} py=${item.ratio}`);
  }
}

if (failures.length) {
  console.error(failures.join("\n\n"));
  console.error(`\n${failures.length} mismatch(es)`);
  process.exit(1);
}

console.log(
  `engine matches Python on ${payload.cases.length} cases, ${payload.rule_fixtures.length} rule fixtures, ${payload.text_fixtures.length} text fixtures, ${payload.name_pairs.length} names, ${payload.ratios.length} ratios`,
);
