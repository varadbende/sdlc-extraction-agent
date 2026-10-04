"""
REQ-1 / REQ-3: Deterministic post-processing of a raw extraction result.
No LLM calls here (ADR-0003) — pure code checks against dictionary.json:
  - closed-vocabulary / enum validation (catches e.g. reach_compliance bug)
  - unit mismatch flagging (catches e.g. viscosity P vs cP bug)
  - completeness score (critical attributes only, per classified type)
  - the 9 proactive quality rules (co-occurrence checks)
  - routing: what's confident enough for Extracted_Attributes vs what
    goes to Needs_Review

CONFIDENCE_THRESHOLD is a routing cutoff, not the eval pass/fail threshold
from REQ-4/REQ-5 (that's a separate number defined on the golden set, later).
"""

import json

CONFIDENCE_THRESHOLD = 0.85  # below this, route to Needs_Review regardless of provenance


def load_dictionary(path="dictionary.json"):
    with open(path) as f:
        return json.load(f)


def validate_and_process(result: dict, dictionary: dict) -> dict:
    """
    Takes the raw LLM extraction result + the dictionary, returns:
    {
        "classification": {...},
        "extracted_attributes": [...],   # -> Extracted_Attributes sheet
        "needs_review": [...],           # -> Needs_Review sheet
        "quality_notes": [...],          # -> Quality_Summary sheet (rule hits)
        "completeness_score": float,
        "missing_critical_attributes": [...],
    }
    """
    attr_defs = {a["key"]: a for a in dictionary["attributes"]}
    valid_keys = set(attr_defs.keys())

    classification = result.get("classification", {})
    ingredient_type = classification.get("ingredient_type", "Uncertain")
    raw_attributes = result.get("attributes", {})

    extracted_attributes = []
    needs_review = []

    # --- Per-attribute deterministic checks ---
    for key, entry in raw_attributes.items():
        if key not in valid_keys:
            # Closed vocabulary violation (REQ-1) — the agent invented a key.
            needs_review.append({
                "key": key,
                "value": entry.get("value"),
                "confidence": entry.get("confidence", 0),
                "reason": "SCHEMA VIOLATION: key not in governed dictionary (closed vocabulary breach)",
            })
            continue

        definition = attr_defs[key]
        value = entry.get("value")
        unit = entry.get("unit")
        confidence = entry.get("confidence", 0)
        provenance = entry.get("provenance", "not_found")

        if value == "NOT FOUND" or provenance == "not_found":
            # Legitimately absent — not an error, not routed anywhere.
            continue

        row = {
            "key": key,
            "value": value,
            "unit": unit,
            "source_quote": entry.get("source_quote"),
            "provenance": provenance,
            "confidence": confidence,
        }

        # Check 1: enum validation (catches the reach_compliance bug)
        if definition["data_type"] == "enum":
            allowed = definition.get("allowed_values", [])
            if value not in allowed:
                needs_review.append({
                    **row,
                    "reason": f"SCHEMA VIOLATION: '{value}' is not one of the allowed enum values {allowed}",
                })
                continue

        # Check 2: unit mismatch (catches the viscosity P vs cP bug)
        expected_unit = definition.get("unit")
        if expected_unit and unit and unit != expected_unit:
            needs_review.append({
                **row,
                "reason": f"UNIT MISMATCH: extracted unit '{unit}' does not match expected unit '{expected_unit}' — needs manual conversion/check",
            })
            continue

        # Check 3: routing by confidence / provenance
        if provenance == "inferred" or confidence < CONFIDENCE_THRESHOLD:
            needs_review.append({
                **row,
                "reason": f"Low confidence ({confidence}) or inferred (not explicitly stated) value",
            })
        else:
            extracted_attributes.append(row)

    # --- Completeness score (critical attributes only, REQ-3) ---
    critical_keys = dictionary["critical_by_type"].get(ingredient_type, [])
    found_keys = {
        row["key"] for row in extracted_attributes
    } | {
        row["key"] for row in needs_review if row.get("value") not in (None, "NOT FOUND")
    }
    found_critical = [k for k in critical_keys if k in found_keys]
    missing_critical = [k for k in critical_keys if k not in found_keys]

    completeness_score = (
        round(len(found_critical) / len(critical_keys) * 100, 1)
        if critical_keys else None
    )

    # --- Quality rules (REQ-1's 9 co-occurrence checks) ---
    value_by_key = {k: v.get("value") for k, v in raw_attributes.items()}
    quality_notes = []

    for rule in dictionary.get("quality_rules", []):
        rtype = rule["type"]

        if rtype == "should_co_occur":
            present = [
                k for k in rule["attributes"]
                if value_by_key.get(k) not in (None, "NOT FOUND")
            ]
            if 0 < len(present) < len(rule["attributes"]):
                quality_notes.append({
                    "rule_id": rule["id"],
                    "note": f"{rule['attributes']} should co-occur but only {present} is present. {rule['rationale']}",
                })

        elif rtype == "conditional_should_not_occur":
            cond = rule["condition"]
            cond_value = value_by_key.get(cond["attribute"], "")
            condition_met = cond.get("value_contains", "").lower() in str(cond_value).lower() \
                if "value_contains" in cond else (cond_value == cond.get("value"))
            flagged_value = value_by_key.get(rule["flagged_attribute"])
            if condition_met and flagged_value not in (None, "NOT FOUND"):
                quality_notes.append({
                    "rule_id": rule["id"],
                    "note": f"{rule['flagged_attribute']} = '{flagged_value}' is flagged given {cond}. {rule['rationale']}",
                })

    return {
        "classification": classification,
        "extracted_attributes": extracted_attributes,
        "needs_review": needs_review,
        "quality_notes": quality_notes,
        "completeness_score": completeness_score,
        "missing_critical_attributes": missing_critical,
    }


if __name__ == "__main__":
    import sys
    from extraction_agent import run_extraction

    if len(sys.argv) != 2:
        print("Usage: python validator.py <path_to_pdf>")
        sys.exit(1)

    dictionary = load_dictionary()
    raw_result = run_extraction(sys.argv[1])
    processed = validate_and_process(raw_result, dictionary)

    print(f"Classification: {processed['classification']}")
    print(f"Completeness score: {processed['completeness_score']}")
    print(f"Missing critical attributes: {processed['missing_critical_attributes']}")
    print(f"\n--- Extracted_Attributes ({len(processed['extracted_attributes'])} rows) ---")
    for row in processed["extracted_attributes"]:
        print(f"  {row['key']}: {row['value']} {row.get('unit') or ''}")
    print(f"\n--- Needs_Review ({len(processed['needs_review'])} rows) ---")
    for row in processed["needs_review"]:
        print(f"  {row['key']}: {row['value']}  <-- {row['reason']}")
    print(f"\n--- Quality_Summary notes ({len(processed['quality_notes'])}) ---")
    for note in processed["quality_notes"]:
        print(f"  [{note['rule_id']}] {note['note']}")