# FORGE

**An autonomous multimodal engineering agent for understanding and improving physical systems.**

Built during the Meta Global AI Developer Hackathon.

> FORGE is in early scaffolding. This repository currently contains documentation, architecture, and project structure only. No application code has been implemented yet.

---

## 1. Problem

Understanding and improving a physical mechanical system — a gear train, a shaft assembly, a transmission — normally requires a human engineer to:

1. Observe the system (photos, video, sketches, specs).
2. Build a mental or formal model of how it works (gear ratios, torque paths, constraints).
3. Form a hypothesis about a problem or improvement ("this shaft will overheat under load," "this ratio is wrong for the target RPM").
4. Run or simulate an experiment to test that hypothesis.
5. Verify the result against physical law and tolerances.
6. Propose an improvement and repeat.

This loop is slow, requires specialized expertise, and is hard to scale. Meanwhile, general-purpose AI models are increasingly good at *multimodal reasoning* (interpreting images, describing mechanisms, proposing hypotheses) but are **not reliable at precise physical calculation**. An LLM can describe what a gear train does; it should not be trusted to compute its torque output and declare the result "correct."

## 2. Solution

FORGE pairs multimodal AI reasoning with deterministic physics computation, and keeps a strict boundary between the two.

- **Perception and reasoning** (Meta Model API, Muse Spark, SAM 3.1) observe a system, build a structural model of it, and propose hypotheses about its behavior or possible improvements.
- **Deterministic Python physics tools** perform the actual calculations — gear ratios, torque, RPM, load, constraint checks — using explicit, auditable formulas, not model inference.
- **The AI interprets results it did not compute.** It reads the deterministic tool's output and classifies the hypothesis as verified, rejected, or inconclusive, then decides what to try next.

This separation means FORGE's conclusions about physical reality are only ever as good as its deterministic tools — never a matter of an LLM "guessing" a number that happens to look right.

## 3. Core Workflow

```
OBSERVE → MODEL → HYPOTHESIZE → EXPERIMENT → VERIFY → IMPROVE
```

| Stage | Description |
|---|---|
| **OBSERVE** | Ingest multimodal input (images, video, diagrams, specs) describing a physical system. |
| **MODEL** | Construct a structured, machine-readable representation of the system (components, connections, known parameters, constraints). |
| **HYPOTHESIZE** | The AI agent proposes a specific, falsifiable claim or improvement about the system. |
| **EXPERIMENT** | The agent decides *what* to compute or test; a deterministic Python tool performs the calculation. The AI never calculates the physics itself. |
| **VERIFY** | The agent interprets the deterministic tool's output against the hypothesis and classifies it as verified, rejected, or inconclusive. |
| **IMPROVE** | Based on verified findings, the agent proposes a concrete change and the loop repeats. |

This loop is iterative: FORGE is expected to cycle through it multiple times per system, refining its model and hypotheses as evidence accumulates.

## 4. Architecture (Summary)

See [`docs/architecture.md`](docs/architecture.md) for the full breakdown. At a high level:

- **Frontend**: Next.js/React app for uploading observations, visualizing the modeled system, and reviewing the agent's reasoning and verification trail.
- **Backend**: FastAPI service exposing the OBSERVE → MODEL → HYPOTHESIZE → EXPERIMENT → VERIFY → IMPROVE workflow, with Pydantic models enforcing structured data at every stage.
- **AI reasoning layer**: Meta Model API and Muse Spark for multimodal understanding, hypothesis generation, and result interpretation. SAM 3.1 for visual segmentation/perception of mechanical components. Muse Spark Open as a potential independent second opinion for verification.
- **Deterministic physics layer**: Plain Python modules implementing gear/shaft/torque/RPM calculations and constraint checks. No LLM involvement in these computations.

## 5. Meta AI Usage

FORGE is designed to use the following Meta AI technologies:

- **Meta Model API** — core reasoning: interpreting observations, generating hypotheses, interpreting deterministic tool output. Accessed through **one** API credential; the specific model (a Muse Spark model, a SAM model) is selected per call, not via separate per-model keys — see `.env.example`.
- **Muse Spark** — multimodal reasoning across combined image/text/structured-data input describing a mechanical system.
- **SAM 3.1** — visual perception and segmentation, used to identify and isolate mechanical components (gears, shafts, housings) from images or video.
- **Muse Spark Open** (potential) — an independently-run model used as a second, cross-checking interpretation of experiment results, to reduce the risk of a single model's reasoning errors going undetected. Not confirmed as a distinct product with its own access requirements; treated as TBD until verified.

No specific Meta API endpoints, SDK methods, or model identifiers are assumed in this repository beyond what's cited from Meta's official hackathon reference workshop in `docs/architecture.md` §10. Remaining integration details will be filled in against the actual, current Meta AI developer documentation once implementation begins.

## 6. Technical Philosophy

**LLMs must not be trusted to calculate or validate physical results directly.**

This is the central architectural rule of FORGE:

- The AI agent's job is to decide *what* needs to be tested and to *interpret* results — not to produce numeric physical answers itself.
- All physical calculations (gear ratios, torque, RPM, forces, tolerances, constraint checks) are performed by deterministic, testable Python functions with no model inference involved.
- Verification outcomes (verified / rejected / inconclusive) are judgments the AI makes *about* a deterministic result, never a substitute for one.
- This keeps FORGE's physical claims auditable: every number in a verification report traces back to a plain Python function, not a model's token prediction.
- This boundary is enforced in code, not by instruction: the agent can only obtain a physical number by calling a named deterministic tool, and it cannot submit a verdict that isn't backed by a real result from one. A confident model cannot shortcut past verification just because it's confident. See `docs/architecture.md` §§3.4–3.5 for how.

This philosophy is intentionally conservative. It trades some flexibility for correctness and auditability, which matters more for a system whose job is to reason about real physical mechanisms.

## 7. Hackathon Scope

FORGE is being built from scratch during the Meta Global AI Developer Hackathon. See [`docs/hackathon.md`](docs/hackathon.md) for track, problem statement, and scope details.

**Initial physical domain:** simple mechanical transmission systems — gears, shafts, RPM, torque, and basic mechanical constraints. This domain is deliberately narrow for the hackathon; the architecture is intended to generalize to other physical domains later, but no such generalization is implemented yet.

## 8. Project Status

This repository currently contains:

- This README
- `docs/architecture.md` — proposed architecture and data flow
- `docs/hackathon.md` — hackathon context and scope
- Initial empty backend/frontend directory structure
- `.gitignore`, `.env.example`, `requirements.txt`

No application logic, AI integrations, or physics tools have been implemented yet.

This architecture was reviewed once against Meta's official hackathon reference workshop, [`meta-models/legal-agent-workshop`](https://github.com/meta-models/legal-agent-workshop), for architectural patterns only — not its legal domain, code, or prompts. See `docs/architecture.md` §10 for what was adopted, what was deliberately left out, and a credential correction to `.env.example`.

## 9. Running Locally

**Backend** (FastAPI):

```bash
cd backend
pip install -r ../requirements.txt
uvicorn app.main:app --reload
```

Runs at `http://localhost:8000`. Run the test suite with `pytest` from `backend/`.

**Frontend** (Next.js demo UI — see [`frontend/README.md`](frontend/README.md) for details):

```bash
cd frontend
npm install
npm run dev
```

Runs at `http://localhost:3000` and calls the backend above. Configure the backend URL via `NEXT_PUBLIC_FORGE_API_URL` (see `frontend/.env.example`); configure which frontend origins the backend accepts via `FORGE_CORS_ORIGINS` (see `.env.example`) — both default to the values above for local development.

The frontend's scenario selector currently runs against **deterministic synthetic perception fixtures** (`simple_gear_pair`, `compound_gear_train`, `uncertain_gear_pair`) served by the backend, not real image analysis — this will later be replaced by SAM-backed perception without changing the rest of the pipeline.
