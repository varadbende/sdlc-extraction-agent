# Requirements — Document Extraction Agent (Project A)

**Phase:** 1 — Requirements
**Status:** Draft, pending approval
**Exit gate:** All 8 requirements below are reviewed and approved before Phase 2 (Design) starts. Once approved, each ID below is referenced in every branch name, commit message, and pull request tied to that requirement — this file is the single source of truth for what each ID means.

**How IDs work:** The IDs (`REQ-1`...`REQ-8`) aren't created in any external system — they're created right here, by writing them into this document and committing it to the repo. That commit is what makes them "official." From here on, a branch like `feature/REQ-3-extraction-schema` or a commit message like `REQ-3: add confidence scoring` is what creates the traceability — the ID in the file is just the definition; the ID used in Git history is what proves the link. (Optional: you can also open a matching GitHub Issue or Jira ticket per REQ ID if you want a visual board to track status — not required for traceability itself, since the Git references already do that job.)

---

## REQ-1 — Governed Attribute Dictionary

**As** the data owner, **I want** a single governed dictionary of 54 standardized attribute keys grouped into 5 categories (Identification & Classification, Physical & Chemical Properties, Regulatory & Compliance, Commercial/Supply Chain, Quality Documentation & Traceability), **so that** extraction output is always structured against a known, controlled vocabulary rather than whatever wording a supplier TDS happens to use.

**Acceptance Criteria:**
- All 54 keys defined with name, group, data type, and expected unit (where applicable).
- A mapping exists from each of the 5 ingredient types (Pharma Excipient/API, Cosmetic, Food Additive, Industrial Chemical, Agrochemical) to its subset of "critical" keys.
- A set of proactive co-occurrence quality rules is defined (e.g., USP/NF and Ph.Eur. compliance should co-occur; GMO status and inorganic pigment should never co-occur).
- The dictionary lives as a version-controlled file, changeable only via pull request.

---

## REQ-2 — Golden/Reference Set

**As** the evaluator, **I want** a hand-annotated golden set of 5 supplier TDS PDFs (drawn from the 10-document stratified sample) labeled against the dictionary — including attributes that are genuinely absent from the source — **so that** the eval suite measures real extraction accuracy rather than the agent grading its own homework.

**Acceptance Criteria:**
- 5 documents fully hand-annotated before any agent code is written.
- Annotations include explicit "not present in source" labels, not just filled values.
- Golden set stored separately from any agent output, under version control.

---

## REQ-3 — Extraction Agent

**As** the PM standing in for the business user, **I want** an agent that reads a supplier TDS PDF and extracts values for the 54 dictionary attributes, **so that** attribute data entry is automated instead of manual.

**Acceptance Criteria:**
- Output follows the governed schema: attribute, key, value, unit, test condition, test method, source, reference.
- Every extracted value carries a provenance tag — stated-in-document vs. inferred vs. web-search fallback.
- High-confidence, explicitly-stated values go to an `Extracted_Attributes` sheet, with source and any conflict flag.
- Low-confidence, inferred, or web-fallback values go to a `Needs_Review` sheet, with a confidence score and the specific reason it was flagged.
- A `Quality_Summary` sheet reports ingredient-type classification, a completeness score (coverage of critical attributes for that type), consistency notes (co-occurrence rule violations), and plausibility notes.

---

## REQ-4 — Deterministic + LLM-Judge Evaluation Suite

**As** the evaluator, **I want** an evaluation suite that checks deterministic, machine-verifiable criteria in code first (exact match, unit normalization, enum membership, schema validation, required-field presence, correct absence) and falls back to an LLM judge only for groundedness and plausibility checks that code can't verify, **so that** evaluation cost and reliability are both optimized.

**Acceptance Criteria:**
- Deterministic checks run at zero LLM token cost.
- LLM-judge checks are scoped only to groundedness (is the value supported by its cited passage?) and plausibility (is an inferred test condition reasonable?).
- A composite pass threshold (numeric) and a separate hard floor (any single critical failure fails the run regardless of composite score) are both defined.
- The suite runs against the golden set (REQ-2), not live/unlabeled documents.

---

## REQ-5 — CI Quality Gate

**As** the release owner, **I want** the evaluation suite to run automatically as a GitHub Actions step on every pull request, blocking merge if results fall below threshold, **so that** agent quality is a release gate, not a report someone reads after the fact.

**Acceptance Criteria:**
- Workflow triggers on PR to main.
- A deliberately broken extraction change is demonstrated blocking the PR.
- The same PR, once fixed, is demonstrated clearing the gate.
- Gate status is visible directly in the PR checks, not just in a log file.

---

## REQ-6 — PR Review Agent (Propose, Never Approve)

**As** the repo owner, **I want** an automated agent to leave a first-pass review comment on every PR, but with no technical ability to approve or merge it, **so that** human approval remains a hard gate.

**Acceptance Criteria:**
- Agent posts a comment (via a bot/Action identity) on PR open or update.
- GitHub branch protection settings (not documentation) are configured so the agent's identity cannot satisfy the "required approval" check.
- Admin bypass is disabled on the protected branch (empty bypass list).

---

## REQ-7 — Human Review Queue

**As** the data steward, **I want** every low-confidence or inferred extraction routed to a human review queue implemented as GitHub Issues (created via API), with the confidence score and flag reason attached, **so that** human judgment is applied exactly where the agent is least certain.

**Acceptance Criteria:**
- One issue created per flagged *document* (not per attribute); the issue body lists every flagged attribute for that document.
- Issue body includes, per flagged attribute: attribute, extracted value, confidence score, reason flagged — plus the source document name once at the top.
- Issue is labeled distinctly (e.g., `needs-review`) for filtering.

---

## REQ-8 — Observability

**As** the program owner, **I want** run-level logs capturing override rate (how often a human review changes the agent's answer) and eval pass rate over time, **so that** I can show agent performance as an operating metric, not a one-time demo.

**Acceptance Criteria:**
- Each agent run produces a structured log entry (timestamp, document, pass/fail per check, token cost).
- Override rate is computable from review-queue (REQ-7) resolutions vs. original agent output.
- Eval pass rate is trackable run-over-run to detect drift.
- Observability covers the **operate/production phase** (live runs on new documents), distinct from the one-time eval (REQ-4) run against the fixed golden set during testing.

---

*End of Phase 1 draft. Awaiting approval and the REQ-7 decision before proceeding to Phase 2 — Design.*

## Change Log

- **2026-10-04**: REQ-2's golden set was reduced from the originally planned 5 hand-annotated documents to 2 (both epoxy resin, different suppliers: EPON 828 / Westlake, EC157 / Elantas Camattini), due to time constraints on this portfolio build. Consequence: REQ-4's eval suite is validated within one resin family only, not across the polyester/PVC families originally planned for stratified coverage. This is a scope reduction, not a technical limitation of the approach — the same process would extend to the remaining 3 documents if time allowed.
