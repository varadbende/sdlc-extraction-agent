#!/usr/bin/env python3
"""
Validates dictionary.json against REQ-1's acceptance criteria:
  - Exactly 54 attribute keys, no duplicates
  - Every attribute's group is one of the 5 declared groups
  - Every key referenced in critical_by_type actually exists in attributes
  - Every quality_rule references attributes that actually exist

This is a deterministic check (ADR-0003) — no LLM involved. It runs standalone
here in Phase 2, and the same function is what REQ-5's CI quality gate will
call on every PR that touches dictionary.json.

Usage:
    python validate_dictionary.py [path/to/dictionary.json]
Exit code 0 = valid, 1 = invalid (prints every problem found, not just the first).
"""

import json
import sys
from collections import Counter

EXPECTED_KEY_COUNT = 54


def validate(path: str) -> list[str]:
    """Returns a list of error strings. Empty list means the file is valid."""
    errors = []

    with open(path) as f:
        data = json.load(f)

    attributes = data.get("attributes", [])
    keys = [a["key"] for a in attributes]
    valid_groups = set(data.get("groups", []))

    # 1. Key count and uniqueness
    if len(keys) != EXPECTED_KEY_COUNT:
        errors.append(f"Expected {EXPECTED_KEY_COUNT} attribute keys, found {len(keys)}")

    dupes = [k for k, count in Counter(keys).items() if count > 1]
    if dupes:
        errors.append(f"Duplicate keys found: {dupes}")

    # 2. Every attribute's group must be declared
    for a in attributes:
        if a.get("group") not in valid_groups:
            errors.append(f"Attribute '{a.get('key')}' has undeclared group '{a.get('group')}'")

    key_set = set(keys)

    # 3. critical_by_type must only reference real keys
    for ingredient_type, critical_keys in data.get("critical_by_type", {}).items():
        missing = [k for k in critical_keys if k not in key_set]
        if missing:
            errors.append(f"critical_by_type['{ingredient_type}'] references unknown keys: {missing}")
        if len(set(critical_keys)) != len(critical_keys):
            errors.append(f"critical_by_type['{ingredient_type}'] has duplicate keys")

    # 4. quality_rules must only reference real keys
    for rule in data.get("quality_rules", []):
        referenced = rule.get("attributes", [])
        if "flagged_attribute" in rule:
            referenced = referenced + [rule["flagged_attribute"]]
        if "condition" in rule and "attribute" in rule["condition"]:
            referenced = referenced + [rule["condition"]["attribute"]]
        missing = [k for k in referenced if k not in key_set]
        if missing:
            errors.append(f"quality_rule '{rule.get('id')}' references unknown keys: {missing}")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "dictionary.json"
    errors = validate(path)

    if errors:
        print(f"FAILED: {len(errors)} issue(s) found in {path}\n")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print(f"OK: {path} is valid (54 keys, no duplicates, all references resolve)")
    sys.exit(0)


if __name__ == "__main__":
    main()
