"""
REQ-4: Deterministic evaluation suite — runs the full pipeline (extraction +
validation, ADR-0003) against every document in golden/ that has a matching
PDF, and checks the PIPELINE'S FINAL ANSWER, not the raw model call alone.

This distinction matters: the validator (validator.py) already exists to
catch bad/ungrounded enum values and quarantine them in Needs_Review with
counts_as_found=False. A hallucination the validator correctly quarantines
is the system working as designed, not a failure — so this suite scores the
validated/processed output. Only a hallucination that slips PAST validation
(reaches Extracted_Attributes, or a trusted Needs_Review row) counts as a
real miss.

Checks:
  - Presence/absence match: did the pipeline's final, trustworthy answer
    correctly say NOT FOUND where the golden set says NOT FOUND?
  - Enum exact match: for enum fields the pipeline trusted, does the value
    exactly equal the golden value?

KNOWN GAP (honest limitation, not hidden): this suite does NOT yet include
the LLM-judge half of ADR-0003 (groundedness/plausibility of free-text field
*content*, e.g. is "liquid" vs "clear liquid" close enough) because no
second cross-vendor judge model is deployed yet per ADR-0002. Groundedness
for ENUM fields specifically is now checked deterministically inside
validator.py itself (source_quote must appear in the document) — that part
no longer needs an LLM judge.

Scoring:
  - composite_pass_rate: overall presence/absence + enum match rate
  - HARD FLOOR: any hallucinated/incorrect enum value that the validator
    nonetheless trusted fails the run regardless of composite score —
    compliance fields being wrong, undetected, is the highest-cost failure
    mode for this project's stated regulated-data use case.
"""

import glob
import json
import os
import sys

from extraction_agent import run_extraction
from pdf_reader import extract_text
from validator import load_dictionary, validate_and_process

COMPOSITE_PASS_THRESHOLD = 0.80  # 80% of checked fields must match
HARD_FLOOR_VIOLATION = "a hallucinated/incorrect enum value passed validation and would have reached a user as trustworthy"


def _is_not_found(value) -> bool:
    return value is None or str(value).strip().upper().startswith("NOT FOUND")


def evaluate_document(pdf_path: str, golden_path: str, dictionary: dict) -> dict:
    with open(golden_path) as f:
        golden = json.load(f)

    raw_text = extract_text(pdf_path)
    raw_result = run_extraction(pdf_path)
    processed = validate_and_process(raw_result, dictionary, raw_text=raw_text)

    # "Trustworthy" = the pipeline's FINAL answer per key, after validation:
    # confidently accepted, or flagged for human review but still a real,
    # grounded, schema-valid value. A key the validator quarantined
    # (counts_as_found=False) asserted nothing trustworthy — for evaluation
    # purposes that's equivalent to NOT FOUND, since the deterministic gate
    # already caught it.
    trustworthy = {}
    for row in processed["extracted_attributes"]:
        trustworthy[row["key"]] = row["value"]
    for row in processed["needs_review"]:
        if row.get("counts_as_found"):
            trustworthy[row["key"]] = row["value"]

    attr_defs = {a["key"]: a for a in dictionary["attributes"]}

    checks = []
    hard_floor_failures = []

    for key, golden_value in golden["attributes"].items():
        if key not in attr_defs:
            continue  # golden file key not in current dictionary version — skip, don't crash

        golden_absent = _is_not_found(golden_value)
        agent_absent = key not in trustworthy
        agent_value = trustworthy.get(key)

        # Check 1: presence/absence match, against the pipeline's FINAL answer
        presence_match = (golden_absent == agent_absent)
        checks.append({
            "key": key,
            "check": "presence_absence",
            "pass": presence_match,
            "golden": "NOT FOUND" if golden_absent else "(has value)",
            "agent": "NOT FOUND" if agent_absent else "(has value)",
        })

        definition = attr_defs[key]

        if not presence_match and golden_absent and not agent_absent and definition["data_type"] == "enum":
            hard_floor_failures.append(
                f"{key}: validated pipeline trusted value '{agent_value}' where golden set says NOT FOUND "
                f"({HARD_FLOOR_VIOLATION})"
            )

        # Check 2: enum exact match, only among values the pipeline trusted
        if not golden_absent and definition["data_type"] == "enum":
            enum_match = (not agent_absent) and (str(agent_value) == str(golden_value))
            checks.append({
                "key": key,
                "check": "enum_exact_match",
                "pass": enum_match,
                "golden": golden_value,
                "agent": agent_value,
            })
            if not enum_match and not agent_absent:
                hard_floor_failures.append(
                    f"{key}: enum mismatch in validated output — golden='{golden_value}', agent='{agent_value}' "
                    f"({HARD_FLOOR_VIOLATION})"
                )

    total = len(checks)
    passed = sum(1 for c in checks if c["pass"])
    composite_pass_rate = round(passed / total, 3) if total else 0.0

    hard_floor_passed = len(hard_floor_failures) == 0
    overall_pass = hard_floor_passed and composite_pass_rate >= COMPOSITE_PASS_THRESHOLD

    return {
        "document": os.path.basename(pdf_path),
        "composite_pass_rate": composite_pass_rate,
        "checks_total": total,
        "checks_passed": passed,
        "hard_floor_passed": hard_floor_passed,
        "hard_floor_failures": hard_floor_failures,
        "overall_pass": overall_pass,
        "checks": checks,
    }


def run_eval_suite(golden_dir="golden", pdf_dir="data/tds_pdfs") -> bool:
    dictionary = load_dictionary()
    golden_files = sorted(glob.glob(os.path.join(golden_dir, "*_golden.json")))

    if not golden_files:
        print(f"No golden files found in {golden_dir}/ — nothing to evaluate.")
        return False

    all_results = []
    for golden_path in golden_files:
        base = os.path.basename(golden_path).replace("_golden.json", "")
        pdf_path = os.path.join(pdf_dir, f"{base}.pdf")
        if not os.path.exists(pdf_path):
            print(f"SKIP: no matching PDF for {golden_path} (expected {pdf_path})")
            continue

        print(f"Evaluating {base} ...")
        result = evaluate_document(pdf_path, golden_path, dictionary)
        all_results.append(result)

        status = "PASS" if result["overall_pass"] else "FAIL"
        print(f"  [{status}] composite={result['composite_pass_rate']*100:.1f}% "
              f"({result['checks_passed']}/{result['checks_total']} checks) "
              f"hard_floor={'OK' if result['hard_floor_passed'] else 'VIOLATED'}")
        for failure in result["hard_floor_failures"]:
            print(f"    HARD FLOOR FAILURE: {failure}")

    suite_passed = all(r["overall_pass"] for r in all_results) if all_results else False

    print(f"\n=== Eval Suite Summary ===")
    print(f"Documents evaluated: {len(all_results)}")
    print(f"Composite pass threshold: {COMPOSITE_PASS_THRESHOLD*100:.0f}%")
    print(f"Hard floor: any hallucinated/incorrect enum value that passed validation fails the run regardless of score")
    print(f"KNOWN GAP: LLM-judge groundedness/plausibility checks for free-text field CONTENT not yet included (no judge model deployed). Enum-field groundedness is now covered deterministically in validator.py.")
    print(f"Suite result: {'PASS' if suite_passed else 'FAIL'}")

    return suite_passed


if __name__ == "__main__":
    passed = run_eval_suite()
    sys.exit(0 if passed else 1)
