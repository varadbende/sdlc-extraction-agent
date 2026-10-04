"""
REQ-3: Core extraction call to the Azure AI Foundry model.
Pass 1: classify + extract against the governed dictionary, print raw JSON.
Excel writing and quality-rule checks come in a later pass, once this
output looks right.

Temperature is 0 everywhere (per your locked decision) — deterministic,
reproducible output is the point; we are not looking for creative variation.
"""

import json
import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI

from pdf_reader import extract_text

load_dotenv()
print("DEBUG endpoint:", repr(os.environ.get("AZURE_FOUNDRY_ENDPOINT")))

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_FOUNDRY_ENDPOINT"],
    api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
    api_version="2024-12-01-preview",
)
DEPLOYMENT = os.environ["AZURE_FOUNDRY_DEPLOYMENT_NAME"]

with open("dictionary.json") as f:
    DICTIONARY = json.load(f)


def build_prompt(document_text: str) -> str:
    key_list = [a["key"] for a in DICTIONARY["attributes"]]
    ingredient_types = DICTIONARY["critical_by_type"].keys()

    return f"""You are extracting structured attribute data from a supplier technical data sheet (TDS).

STEP 1 — CLASSIFY the product into exactly one of these ingredient types: {list(ingredient_types)}.
Base this ONLY on evidence in the document (e.g., "USP/NF monograph referenced" -> Pharma Excipient/API,
"INCI name given" -> Cosmetic Ingredient). You MUST quote the exact phrase from the document that led to
your classification. If evidence is mixed or absent, classify as "Uncertain" and list the contenders instead
of guessing.

STEP 2 — EXTRACT a value for each of these 54 attribute keys, and ONLY these keys (closed vocabulary,
never invent a key): {key_list}

For each key, return:
- "value": the extracted value, or "NOT FOUND" if the document does not state or imply it
- "unit": the unit if applicable, else null
- "source_quote": the EXACT phrase from the document that supports this value (verbatim substring — this
  will be checked against the source text). Use "NOT FOUND" if value is "NOT FOUND".
- "provenance": one of "stated" (explicitly in the document), "inferred" (reasonably implied but not
  stated outright), or "not_found"
- "confidence": a number from 0.0 to 1.0 reflecting how certain you are this value is correct

Return ONLY valid JSON in this exact shape, no other text:
{{
  "classification": {{
    "ingredient_type": "<one of the 5 types or 'Uncertain'>",
    "evidence_quote": "<exact phrase from document, or list of contenders if Uncertain>"
  }},
  "attributes": {{
    "<key>": {{"value": ..., "unit": ..., "source_quote": ..., "provenance": ..., "confidence": ...}},
    ...
  }}
}}

DOCUMENT TEXT:
{document_text}
"""


def run_extraction(pdf_path: str) -> dict:
    document_text = extract_text(pdf_path)
    prompt = build_prompt(document_text)

    response = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extraction_agent.py <path_to_pdf>")
        sys.exit(1)

    result = run_extraction(sys.argv[1])
    print(json.dumps(result, indent=2))