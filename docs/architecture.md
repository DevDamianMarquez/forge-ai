# FORGE — Proposed Architecture

> Status: proposed, not implemented. This document describes the intended structure and data flow for FORGE at the start of the Meta Global AI Developer Hackathon. Details will evolve as implementation proceeds.
>
> Reviewed once against Meta's official hackathon reference, [`meta-models/legal-agent-workshop`](https://github.com/meta-models/legal-agent-workshop) — studied for architectural patterns only. See §10 for what that review changed and what it deliberately didn't.

## 1. Goals of This Architecture

1. Keep a hard boundary between AI reasoning and physical calculation.
2. Make every stage of the OBSERVE → MODEL → HYPOTHESIZE → EXPERIMENT → VERIFY → IMPROVE loop a distinct, inspectable step with a defined data shape.
3. Keep the initial scope small and concrete: simple mechanical transmission systems (gears, shafts, RPM, torque, constraints).
4. Avoid premature generalization — no plugin system, no multi-domain abstraction layer, no speculative extensibility until the core loop works for one domain.

## 2. High-Level Components

```
┌─────────────────────┐        ┌──────────────────────────┐
│   Frontend (Next.js) │  HTTP  │   Backend (FastAPI)       │
│   - Upload observations        - Orchestrates the loop   │
│   - Visualize system model    - Pydantic schemas          │
│   - Show reasoning/verdicts    - Calls AI + physics layers│
│   - Show run trace (§6)        - Persists run trace (§6)  │
└─────────────────────┘        └──────────────────────────┘
                                          │
                     ┌────────────────────┼─────────────────────┐
                     ▼                                          ▼
        ┌───────────────────────────┐          ┌───────────────────────────┐
        │  AI Reasoning Layer        │          │  Deterministic Physics     │
        │  - Meta Model API          │          │  Layer                     │
        │    (one credential; model  │          │  - Pure Python functions   │
        │    selected per call)      │          │  - Gear/shaft/torque math  │
        │  - Muse Spark (multimodal) │          │  - Constraint checks       │
        │  - SAM 3.1 (segmentation)  │          │  - No model inference      │
        │  - Muse Spark Open (opt.,  │          │                            │
        │    credential unconfirmed) │          │                            │
        │                            │          │                            │
        │  Produces: models,         │          │  Produces: numeric,        │
        │  hypotheses, verdicts      │          │  deterministic results     │
        └───────────────────────────┘          └───────────────────────────┘
```

The backend is the only component permitted to call either layer. The frontend never talks to Meta AI services or the physics layer directly.

## 3. The Core Loop as a Data Pipeline

Each stage consumes a Pydantic model and produces the next. This keeps the loop auditable and lets any stage be tested or replayed independently.

```
Observation  →  SystemModel  →  Hypothesis  →  ExperimentResult  →  Verdict  →  Improvement
   (OBSERVE)      (MODEL)       (HYPOTHESIZE)    (EXPERIMENT)        (VERIFY)     (IMPROVE)
```

### 3.1 OBSERVE

- **Input**: images, video frames, diagrams, free-text specs/notes about a mechanical system.
- **Processing**: SAM 3.1 identifies and segments visible components (gears, shafts, housings). Muse Spark performs multimodal interpretation of the combined visual + text input.
- **Output**: an `Observation` record — raw inputs plus extracted visual/textual annotations. No physical claims are made yet.

### 3.2 MODEL

- **Input**: one or more `Observation` records.
- **Processing**: the AI reasoning layer proposes a structured `SystemModel` — components, their types (gear, shaft, coupling), known or estimated parameters (tooth count, diameter, material), and connections/constraints between them.
- **Output**: a `SystemModel`. This is still AI-proposed structure, not a verified physical result — it is the thing hypotheses will be tested against.

### 3.3 HYPOTHESIZE

- **Input**: a `SystemModel`.
- **Processing**: the AI agent proposes a specific, falsifiable `Hypothesis` — e.g., "the output shaft RPM exceeds the rated limit under the given input RPM and gear ratio," or "this gear ratio does not achieve the target torque multiplication."
- **Output**: a `Hypothesis` record naming exactly what will be tested and what would count as confirmation or rejection.

### 3.4 EXPERIMENT

- **Input**: a `Hypothesis` and the relevant `SystemModel` parameters.
- **Processing**: the AI agent selects a tool from a small, fixed registry of deterministic physics tools (e.g. `compute_gear_ratio`, `compute_output_torque`, `compute_output_rpm`, `check_constraint`) via standard tool/function calling against the Meta Model API, and supplies the arguments. **The backend — never the model — executes the matching Python function.** The numeric result is returned to the conversation as a tool result, not generated as text by the model.
- **Output**: an `ExperimentResult` — the raw, deterministic numeric output plus the inputs used to produce it, and which tool computed it.
- **Enforcement**: the agent can only ever obtain a physical number by naming one of these tools; there is no code path where the model's own text output is accepted as a measurement. This mirrors the reference workshop's tool-registry pattern (one file per tool, a fixed `definitions()`/`run()` contract) adapted to physics calculations instead of document/case actions.

### 3.5 VERIFY

- **Input**: a `Hypothesis` and its corresponding `ExperimentResult`.
- **Processing**: the AI agent compares the deterministic result against the hypothesis's stated success/failure criteria and classifies the outcome.
- **Output**: a `Verdict` — one of `verified`, `rejected`, or `inconclusive`, with the AI's reasoning. Optionally cross-checked by Muse Spark Open as an independent second interpretation before finalizing.
- **Enforcement**: submitting a `Verdict` is itself a tool call the backend validates before accepting — it is refused if it doesn't reference a real, previously-produced `ExperimentResult` for that exact `Hypothesis`. A model cannot shortcut straight to "verified" without the EXPERIMENT round-trip having actually happened; this is checked in code, not requested by instruction. See §10 for where this pattern came from.

### 3.6 IMPROVE

- **Input**: one or more `Verdict`s for a given `SystemModel`.
- **Processing**: the AI agent proposes a concrete modification to the system (e.g., change gear ratio, change shaft diameter) intended to address a rejected hypothesis.
- **Output**: an `Improvement` proposal, which can feed back into a new `SystemModel` and restart the loop (HYPOTHESIZE again against the revised model).

## 4. Backend Structure (FastAPI)

Proposed initial layout (structure only — no logic yet):

```
backend/
  app/
    api/            # FastAPI routers, one per workflow stage (observe, model, hypothesize, experiment, verify, improve)
    core/           # settings, config loading
    models/         # Pydantic schemas: Observation, SystemModel, Hypothesis, ExperimentResult, Verdict, Improvement
    physics/        # deterministic calculation modules (gears, shafts, torque, constraints)
    services/       # thin wrappers around Meta Model API / Muse Spark / SAM 3.1 calls
  tests/
```

Key rule: `app/physics/` contains plain, deterministic, unit-testable Python with **zero** dependencies on AI services. Everything in `app/services/` is the only place allowed to call out to Meta AI models.

## 5. Frontend Structure (Next.js/React)

Proposed initial layout (structure only — no logic yet):

```
frontend/
  app/            # routes/pages
  components/      # UI components (upload, model viewer, hypothesis/verdict timeline)
  lib/             # API client for the FastAPI backend
```

The frontend's job is to let a user feed in observations and watch the loop proceed — surfacing the `SystemModel`, each `Hypothesis`, its `ExperimentResult`, and the resulting `Verdict` — not to perform any reasoning or calculation itself.

## 6. Run Trace and Observability

Every pass through the loop for one `SystemModel` is a **run**, identified by a run id. As each stage completes, the backend appends one entry to that run's trace: which stage ran, a summary of its input, which tool (if any) was called and with what arguments, and what came back. The trace is returned by a single read endpoint and is what the frontend renders as a timeline — the agent's decision, the deterministic result, and the verdict, side by side, for every step.

This is deliberately lightweight for the hackathon: an append-only list persisted with the run (in-memory or a flat file is enough), not a database, dashboard, or operator console. The point is that the AI's reasoning and the deterministic tool's output are never collapsed into a single opaque "answer" — both remain visible, per step, after the run finishes. This is scoped down from the full operator console the reference workshop builds (see §10); FORGE needs the trace to exist, not a UI for humans to act on it mid-run.

## 7. Iteration Limits and Escalation

The HYPOTHESIZE → EXPERIMENT → VERIFY cycle is bounded, so a confused agent cannot spin forever:

- A given `Hypothesis` gets a small, fixed number of VERIFY attempts (e.g. 3) before it is marked `inconclusive` and the loop moves on rather than retrying indefinitely.
- A given `SystemModel` gets a capped number of HYPOTHESIZE → IMPROVE cycles per run.
- Either cap being hit sets a simple `needs_review` flag on the run rather than failing silently or looping — there is no human-in-the-loop workflow (approvals, sign-off, evidence requests) in this hackathon's scope; the flag is enough to make a stuck run visible in the trace (§6).

## 8. Why This Separation Matters

If the AI reasoning layer and the deterministic physics layer were blurred together — e.g., asking an LLM to "calculate the output torque" directly — FORGE's conclusions about real mechanical systems would be only as reliable as the model's arithmetic and physics recall, which is not an acceptable failure mode for a system meant to reason about physical hardware. By forcing every numeric physical claim through a plain Python function, FORGE's results stay auditable: any verdict can be traced back to a deterministic calculation that can be independently checked, tested, and trusted — regardless of how good or poor the AI's reasoning about *when* to run it was.

## 9. Explicitly Out of Scope (for now)

- Multi-domain generalization beyond simple mechanical transmission systems.
- Real-time control or hardware-in-the-loop testing.
- Any specific Meta API endpoint, SDK call, or model identifier beyond what's cited in §10 from the official hackathon reference — remaining integration details will be confirmed against current Meta AI developer documentation before implementation.
- Authentication, multi-user support, persistence beyond what's needed to demo the loop.
- A human review/escalation workflow (approvals, evidence requests, sign-off) — §7's `needs_review` flag is the full extent of this for the hackathon.

## 10. Patterns Reviewed Against Meta's Reference Workshop

Meta's official hackathon reference, [`meta-models/legal-agent-workshop`](https://github.com/meta-models/legal-agent-workshop), is a workshop for building a legal document-investigation agent. It was reviewed once, for architectural and integration patterns only — its legal domain, prompts, tools, and case data were not used and do not appear anywhere in FORGE.

**Adopted:**

| Pattern in the reference | Applied to FORGE as |
|---|---|
| A fixed registry of one-file-per-tool definitions, with the model choosing a tool name and arguments and the harness executing the real function | §3.4's EXPERIMENT tool registry (`compute_gear_ratio`, `compute_output_torque`, etc.) |
| The check that matters (their memo/checklist verification) runs *inside* the tool call the model must use to proceed, not as a tool the model can choose to skip | §3.5: a `Verdict` submission is refused unless it references a real `ExperimentResult` — enforced in code at the point of submission, the same way their `submit_memo` cannot pass without the memo rules running |
| Ground truth (their per-case checklist) lives outside the agent's visible workspace entirely | Already true in FORGE's design and reaffirmed: the physics layer's calculations happen outside the AI reasoning layer and are never seeded to the model as "expected answers" it could anchor on |
| A turn/retry limit so a stuck agent doesn't loop forever, escalating instead | §7's bounded VERIFY attempts and HYPOTHESIZE→IMPROVE cycles |
| Per-turn progress saved so a run can be inspected after the fact | §6's run trace |
| A single API credential, with the specific model chosen per call rather than one key per model | `.env.example` now has one `META_MODEL_API_KEY` instead of the separate per-model keys drafted earlier |

**Deliberately not adopted** (out of scope for this hackathon, or specific to the legal domain):

- The full human-reviewer workflow — handoff cards, evidence release, attorney sign-off with approve/reject-with-notes. FORGE uses a single `needs_review` flag (§7) instead of building a reviewer UI or multi-step escalation protocol.
- The pre-built Agent Console as an *operational* tool (releasing evidence, answering requests, approving memos mid-run). FORGE's observability goal is a read-only trace (§6), not a console a human acts through during a run.
- Document-specific plumbing: a Files API ingestion pipeline, quote-checked facts against page text, signature verification, privilege/confidentiality flagging. All specific to reading legal documents; none apply to observing a mechanical system.
- A case-management "record" system mirroring theirs. FORGE's `Observation` / `SystemModel` / `ExperimentResult` / `Verdict` records already serve this role for the physical domain.
- Any workflow about *how the agent's own code gets written* (their Session 1/2 structure, ground-rules prompts for a coding assistant). That's about building their agent with a coding tool, not a pattern for FORGE's runtime architecture.

**Credential correction:** the reference's `agent/.env.example` and `agent_kit/client.py` show one Meta Model API key (their `MODEL_API_KEY`) used against one base URL, with the model (e.g. a Muse Spark model, a SAM model) selected per call by name — not a separate key per model. FORGE's `.env.example` had speculatively invented `MUSE_SPARK_API_KEY`, `MUSE_SPARK_OPEN_API_KEY`, and `SAM_API_KEY`; those are removed. FORGE now has a single `META_MODEL_API_KEY` placeholder, with the exact variable name, base URL, and model identifiers for FORGE's own integration left as TBD pending the current official Meta AI developer docs — the workshop is one dated reference, not a guarantee of FORGE's final config. "Muse Spark Open" does not appear anywhere in the reference at all; its existence as a separate product and any credential it might need remain unconfirmed and are marked TBD rather than guessed at.
