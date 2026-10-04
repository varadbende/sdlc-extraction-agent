# Architecture Decision Records — Project A

Phase 2 — Design. Each ADR: Status, Context, Decision, Alternatives Considered, Consequences.

---

## ADR-0001: Trunk-Based Development over Git Flow

**Status:** Accepted

**Context:** The agent quality gate (REQ-5) must evaluate what's actually about to ship, continuously — not lag behind a drifted long-lived branch.

**Decision:** Trunk-based development: short-lived feature branches off `main`, merged via PR, with CI quality gate on every PR to `main`. No long-lived `develop` branch.

**Alternatives Considered:**
- Git Flow (`develop`/`release`/`feature`/`hotfix`) — rejected: a `develop` branch can drift from what's released, weakening the "gate reflects reality" guarantee.
- No branching discipline (commit straight to `main`) — rejected: removes the PR review gate (REQ-6) and the space for CI to run before merge.

**Consequences:** Requires short-lived branches and strict branch protection (no `develop` buffer). In return, eval pass/fail always reflects what's one merge from shipping.

---

## ADR-0002: Two Cross-Vendor Model Deployments (Extractor + Judge)

**Status:** Accepted

**Context:** A single model extracting and then grading its own output risks correlated blind spots — it may trust its own mistakes.

**Decision:** Two Azure AI Foundry deployments: a small, cheap extractor (4o-mini class) and a larger, different-family model as judge.

**Alternatives Considered:**
- Same model for extraction and judging — rejected: cheapest, but the judge inherits the extractor's blind spots, undermining the eval's purpose.
- Same vendor, different size (e.g., two OpenAI models) — weaker mitigation than cross-vendor; flagged honestly as a lesser safeguard, not equivalent to true cross-vendor diversity.

**Consequences:** Higher token cost and two deployments to manage, versus meaningfully more independent error detection.

---

## ADR-0003: Deterministic-First Evaluation

**Status:** Accepted

**Context:** Not every check needs an LLM. Using one for everything is slow, costly, and non-reproducible where code can already give a certain answer.

**Decision:** Run deterministic, code-based checks first (exact match, unit normalization, enum membership, schema validation, field presence/absence) at zero token cost. Fire an LLM judge only for groundedness and plausibility — what code can't verify.

**Alternatives Considered:**
- LLM-as-judge for everything — rejected: costs tokens and time even on checks code can do for free, and is non-deterministic where determinism is available.
- Pure code checks, no LLM judge — rejected: can't assess groundedness (is a value truly supported by its cited passage?) or plausibility of inferred values.

**Consequences:** More eval logic to maintain (two check types), but a cheaper, faster, more reproducible suite overall — and it's the design that makes REQ-5's "eval as release gate" affordable to run on every PR.

---

## ADR-0004: Stateless, Short-Term Memory Only

**Status:** Accepted

**Context:** The extraction agent processes one supplier TDS document per run, independent of any other document.

**Decision:** No persistent memory across runs. Each run uses only short-term/working memory — the current document plus the static dictionary/rules loaded fresh each time.

**Alternatives Considered:**
- Episodic memory (remembering past documents/runs) — rejected: risks cross-contamination between unrelated suppliers' data, and no requirement calls for recalling prior runs.
- Semantic memory store (a persistent vector DB of past extractions) — rejected as unnecessary complexity; the governed dictionary is static reference data, not something that needs to be "remembered" or learned over time.
- Procedural memory (learned extraction heuristics that evolve) — rejected: would make behavior drift silently between runs, undermining reproducibility the eval suite depends on.

**Consequences:** Simpler, fully reproducible runs (same input → same output). Trade-off: the agent can't improve from past corrections automatically — the REQ-7 review queue and REQ-8 override tracking are the mechanism for that feedback instead, applied manually to the dictionary/rules.

---

## ADR-0005: Sequential Pipeline Orchestration

**Status:** Accepted

**Context:** The extraction task is a fixed sequence of steps (classify → extract → score → route), not an open-ended task needing dynamic planning.

**Decision:** Sequential orchestration: classify ingredient type → extract against the governed schema → apply quality rules → compute completeness → route low-confidence items to review.

**Alternatives Considered:**
- Router pattern (dispatch to different sub-agents by type) — rejected: all 5 ingredient types share one extraction process against the same 54-key dictionary; only the critical subset differs, which a lookup handles without needing separate agents.
- Planner-executor (agent plans its own steps) — rejected as overkill: the steps are fixed and known in advance, so dynamic planning adds latency and unpredictability with no benefit.

**Consequences:** Easy to trace, test, and debug step-by-step (useful for the interview walkthrough). Trade-off: less flexible if future document types need a genuinely different process — would require revisiting this ADR, not just a config change.

---

## ADR-0006: Golden Set Hand-Built Before Agent Code

**Status:** Accepted

**Context:** An eval suite built after the agent, scored by the agent's own definition of success, risks measuring what the agent does well rather than what's actually correct.

**Decision:** Hand-annotate the 5-document golden set, including deliberately absent attributes, before writing any extraction code.

**Alternatives Considered:**
- Build the golden set from the agent's own early outputs, then correct it — rejected: anchors the "correct" answer to the agent's assumptions instead of ground truth.
- Skip a golden set, use spot-checks only — rejected: gives no basis for a regression/drift check (REQ-8) or a CI gate (REQ-5).

**Consequences:** Upfront manual labeling effort before any code runs. In return, the eval suite measures real accuracy, and "I measured what I didn't invent" becomes a defensible claim.

---

## ADR-0007: Branch Protection with Empty Bypass List

**Status:** Accepted

**Context:** A required check or review that admins can bypass isn't really required — it's advisory.

**Decision:** Enable branch protection on `main` with required PR review and required status checks, and explicitly include admins with no bypass exceptions.

**Alternatives Considered:**
- Standard protection excluding admins (GitHub's default suggestion) — rejected: as the sole admin, this would let the gate be skipped exactly when it's most tempting to skip it — under deadline pressure.

**Consequences:** No shortcut exists even for the repo owner, which is the point: it's demonstrable evidence the gate is real, not just a documented intention.
