"""
Demo layer for Project A -- NOT part of REQ-3's formal acceptance criteria.
Added at the end of the build, explicitly as an interview-demo convenience:
lets you drag-and-drop a TDS PDF and see the governed extraction + validation
pipeline's output in a browser instead of reading raw JSON/Excel from the
terminal. Runs entirely locally (`streamlit run app.py`) -- no new accounts,
no hosting. It calls extraction_agent.py / validator.py / excel_writer.py
exactly as the CLI does; nothing about the underlying pipeline changes.
"""

import os
import tempfile

import streamlit as st

from extraction_agent import run_extraction
from validator import load_dictionary, validate_and_process
from excel_writer import write_workbook
from pdf_reader import extract_text

st.set_page_config(page_title="Document Extraction Agent -- Demo", layout="wide")

st.title("Document Extraction Agent -- Demo")
st.caption(
    "Demo layer only -- not part of REQ-3's formal acceptance criteria. "
    "Upload a supplier technical data sheet (TDS) PDF and watch the governed "
    "extraction + deterministic validation pipeline (ADR-0003) run end to end."
)

uploaded_file = st.file_uploader("Upload a TDS PDF", type=["pdf"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        pdf_path = tmp.name

    with st.spinner("Extracting text (deterministic, no LLM) ..."):
        raw_text = extract_text(pdf_path)

    with st.spinner("Running extraction agent (Azure Foundry call) ..."):
        dictionary = load_dictionary()
        raw_result = run_extraction(pdf_path)

    with st.spinner("Running deterministic validation (ADR-0003) ..."):
        processed = validate_and_process(raw_result, dictionary, raw_text=raw_text)

    classification = processed["classification"]
    st.subheader("Classification")
    col1, col2 = st.columns(2)
    col1.metric("Ingredient Type", classification.get("ingredient_type", "Uncertain"))
    completeness = processed["completeness_score"]
    col2.metric("Completeness Score", f"{completeness}%" if completeness is not None else "N/A")
    st.caption(f"Evidence quote: {classification.get('evidence_quote', 'N/A')}")

    if processed["missing_critical_attributes"]:
        st.warning(f"Missing critical attributes: {', '.join(processed['missing_critical_attributes'])}")

    tab1, tab2, tab3 = st.tabs(["Extracted Attributes", "Needs Review", "Quality Notes"])

    with tab1:
        if processed["extracted_attributes"]:
            st.dataframe(
                [
                    {
                        "Key": r["key"],
                        "Value": r["value"],
                        "Unit": r.get("unit") or "",
                        "Confidence": r.get("confidence"),
                        "Source Quote": r.get("source_quote") or "",
                    }
                    for r in processed["extracted_attributes"]
                ],
                use_container_width=True,
            )
        else:
            st.info("No high-confidence attributes extracted.")

    with tab2:
        if processed["needs_review"]:
            st.dataframe(
                [
                    {
                        "Key": r["key"],
                        "Value": r.get("value"),
                        "Reason Flagged": r["reason"],
                        "Confidence": r.get("confidence"),
                    }
                    for r in processed["needs_review"]
                ],
                use_container_width=True,
            )
        else:
            st.success("Nothing flagged for review.")

    with tab3:
        if processed["quality_notes"]:
            for note in processed["quality_notes"]:
                st.write(f"**[{note['rule_id']}]** {note['note']}")
        else:
            st.info("No quality rule violations detected.")

    output_path = os.path.join(
        tempfile.gettempdir(), f"{uploaded_file.name.rsplit('.', 1)[0]}_extraction.xlsx"
    )
    write_workbook(processed, pdf_path, output_path)
    with open(output_path, "rb") as f:
        st.download_button(
            "Download 3-sheet Excel workbook",
            data=f.read(),
            file_name=os.path.basename(output_path),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload a PDF to run the pipeline.")
