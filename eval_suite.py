"""
REQ-4: Deterministic evaluation suite — runs the agent against every document
in golden/ that has a matching PDF, and checks what code can verify without
judgment calls (ADR-0003):

  - Presence/absence match: did the agent correctly say NOT FOUND where the
    golden set says NOT FOUND, and find something where golden says something
    was found? (This is what catches hallucinations like the ep_compliance /
    reach_compliance ones found during build.)
  - Enum exact match: for enum-typed fields, does the agent's final value
    exactly equal the golden value?

KNOWN GAP (honest limitation, not hidden): this suite does NOT yet include
the LLM-judge half of ADR-0003 (groundedness, plausibility of free-text
values) because no second cross-vendor judge model is deployed yet per
ADR-0002. Free-text field *content* correctness (e.g. is "liquid" vs
"clear liquid" close enough) is therefore not scored here — only whether
something was found at all. This is flagged, not silently skipped.

Scoring:
  - composite_pass_rate: overall presence/absence + enum match rate
  - HARD FLOOR: any hallucinated enum value (schema-valid-looking but wrong,
    or present when golden says NOT FOUND) fails the run regardless of
    composite score — compliance fields being wrong is the highest-cost
    failure mode for this project's stated regulated-data use case.
"""

import glob
import json
import os
import sys

from extraction_agent import run_extraction
from validator import load_dictionary, validate_and_process

COMPOSITE_PASS_THRESHOLD = 0.80  # 80% of checked fields must match
HARD_FLOOR_VIOLATION = "hallucinated or incorrect enum value on a compliance field"


def _is_not_found(value) -> bool:
    return value is None or str(value).strip().upper().startswith("NOT FOUND")


def evaluate_document(pdf_path: str, golden_path: str, dictionary: dict) -> dict:
    with open(golden_path) as f:
        golden = json.load(f)

    raw_result = run_extraction(pdf_path)
    processed = validate_and_process(raw_result, dictionary)

    # Build a flat view of what the agent actually produced per key,
    # from both extracted_attributes and needs_review (we still want to
    # score a flagged value's presence/absence correctness).
    agent_values = {}
    for row in processed["extracted_attributes"] + processed["needs_review"]:
        agent_values[row["key"]] = row.get("value")

    attr_defs = {a["key"]: a for a in dictionary["attributes"]}

    checks = []
    hard_floor_failures = []

    for key, golden_value in golden["attributes"].items():
        if key not in attr_defs:
            continue  # golden file key not in current dictionary version — skip, don't crash

        golden_absent = _is_not_found(golden_value)
        agent_raw = raw_result.get("attributes", {}).get(key, {})
        agent_value = agent_raw.get("value")
        agent_absent = _is_not_found(agent_value)

        # Check 1: presence/absence match (always checkable, zero LLM cost)
        presence_match = (golden_absent == agent_absent)
        checks.append({
            "key": key,
            "check": "presence_absence",
            "pass": presence_match,
            "golden": "NOT FOUND" if golden_absent else "(has value)",
            "agent": "NOT FOUND" if agent_absent else "(has value)",
        })

        if not presence_match and golden_absent and not agent_absent:
            definition = attr_defs[key]
            if definition["data_type"] == "enum":
                hard_floor_failures.append(
                    f"{key}: hallucinated value '{agent_value}' where golden set says NOT FOUND "
                    f"({HARD_FLOOR_VIOLATION})"
                )

        # Check 2: enum exact match (only when golden has a real value and it's an enum field)
        definition = attr_defs[key]
        if not golden_absent and definition["data_type"] == "enum":
            enum_match = (str(agent_value) == str(golden_value))
            checks.append({
                "key": key,
                "check": "enum_exact_match",
                "pass": enum_match,
                "golden": golden_value,
                "agent": agent_value,
            })
            if not enum_match:
                hard_floor_failures.append(
                    f"{key}: enum mismatch — golden='{golden_value}', agent='{agent_value}' "
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
    print(f"Hard floor: any hallucinated/incorrect enum value on a compliance field fails regardless of score")
    print(f"KNOWN GAP: LLM-judge groundedness/plausibility checks not yet included (no judge model deployed)")
    print(f"Suite result: {'PASS' if suite_passed else 'FAIL'}")

    return suite_passed


if __name__ == "__main__":
    passed = run_eval_suite()
    sys.exit(0 if passed else 1)