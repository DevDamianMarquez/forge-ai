# FORGE — Autonomous Physical Systems Engineer

**AI PROPOSES. PHYSICS VERIFIES.**

FORGE analyzes simple mechanical transmissions from an image, keeps a strict boundary between what was *observed* and what was *confirmed*, and uses an AI agent to propose design improvements that a deterministic Python physics engine verifies independently.

Built for the **Meta Global AI Developer Hackathon 2026** (Indie Developer track, "Push the Frontier" problem statement). See [`docs/hackathon.md`](docs/hackathon.md).

- **Live demo:** https://forge-ai-phi-nine.vercel.app
- **Video demo:** https://youtu.be/_5SYOqQ2q04

---

## 1. The problem

Language models can describe how a gear train works, but they are not reliable at precise physical calculation, and a confident wrong number looks exactly like a right one. An AI that "computes" an output speed and declares it correct is not something you can trust with a mechanical system.

FORGE separates the two jobs:

- **AI perceives and proposes.** SAM 3.1 detects components in an image. Muse Spark chooses which design to test.
- **Deterministic code computes and decides.** Plain Python functions calculate gear ratio, output RPM and rotation direction, and constraint code decides PASS or FAIL.
- **Only confirmed facts reach the physics.** A detection is an observation, not a fact, however high its confidence.

## 2. How it works

```
  Image (JPEG / PNG)
        │
        ▼
  SAM 3.1 detection
        │
        ▼
  Observed evidence            every value: observed · inferred · unresolved
        │
        ▼
  Human confirmation           user confirms gears, tooth counts, shafts, meshes, input RPM
        │
        ▼
╔══════════════════════════════════════════════════════════════════╗
║  EVIDENCE BOUNDARY                                               ║
║  Are all required values 'confirmed'?                            ║
║     no  ──► STOP: no PhysicalSystem, structured issues returned  ║
║     yes ──► continue                                             ║
╚══════════════════════════════════════════════════════════════════╝
        │  only confirmed values cross this line
        ▼
  PhysicalSystem built  ──►  topology compiled (single transmission path)
        │
        ▼
  Deterministic experiment     Python: gear ratio, output RPM, direction
        │
        ▼
  Verified result
        │
        ▼  optional: objective, e.g. output_rpm <= target (two-gear systems)
  Muse Spark proposes a design ──► deterministic experiment + constraint check
        ▲                                        │
        └──── FAIL: result returned as evidence ─┤   (max 3 attempts)
                                                 ▼
                                PASS ──► VERIFIED + engineering explanation
```

1. **Observe (SAM 3.1).** The user uploads a JPEG or PNG. The backend sends it to SAM 3.1 through the Meta Model API (OpenAI SDK, Responses API) with a short concept prompt (default `gear`). Detections come back with SAM's confidence score when provided. Image bytes are kept in memory only; they are never written to disk or logged.
2. **Observed evidence.** Detections become a `PerceptionResult` in which every value carries a status: `observed`, `inferred`, `confirmed`, `rejected` or `unresolved`. Nothing is auto-confirmed. The response lists what is still missing (for example, no confirmed shafts, no input RPM).
3. **Human confirmation.** The user explicitly confirms which detections are gears and supplies the physical values: tooth counts, shafts, meshes, input shaft and input RPM.
4. **Evidence boundary.** A deterministic builder (`app/perception/builder.py`) turns perception into a `PhysicalSystem` only if every required value is `confirmed`. Otherwise it builds nothing and returns structured reasons. Confidence never substitutes for confirmation.
5. **Physical model.** The topology compiler (`app/physics/topology.py`) reduces shafts, gears and meshes to a single, unbranched transmission path from the input shaft to the output shaft. Branched, cyclic or disconnected systems are rejected explicitly.
6. **Deterministic experiment and verification.** The physics engine computes the gear ratio, output RPM and output direction. This produces the verified result for the confirmed system.
7. **Autonomous redesign (Muse Spark).** For a verified two-gear system, the user can set an objective such as a maximum output RPM. Muse Spark proposes a candidate by calling the `test_gear_design` tool with two tooth counts. The backend runs the experiment and the constraint check. On FAIL, the result goes back to Muse Spark as evidence and it may propose again, up to 3 attempts. Only a deterministic PASS produces a `verified` status, even if the model's text claims success.
8. **Explanation.** After the outcome is final, the backend writes a plain-language engineering explanation from the structured evidence. It is string formatting over values already computed: no extra model call and no effect on the result.

## 3. Implemented capabilities

- Image upload and SAM 3.1 component detection, shown as overlays marked `OBSERVED`
- Observation statuses and a missing-information list for every analysis
- Explicit user confirmation of physical values before any calculation
- Evidence boundary that refuses unconfirmed values with structured issues
- Topology compiler for single-path gear trains, including compound trains with shared shafts
- Deterministic physics: gear ratio, output RPM, output direction after each external mesh
- Constraint evaluation on `output_rpm` or `gear_ratio` with `lte`, `gte`, `lt`, `gt`, `eq`
- Bounded autonomous redesign with Muse Spark (`muse-spark-1.3`) tool calling: 1 tool, tooth counts between 10 and 120, at most 3 attempts; statuses `verified`, `exhausted` or `model_error`
- Muse Spark analysis endpoint with the `run_gear_train_experiment` tool, bounded to 2 tool rounds and 2 tool calls
- Engineering explanations generated from verified results
- Demo Scenarios mode with three hand-authored perception fixtures: `simple_gear_pair`, `compound_gear_train`, `uncertain_gear_pair` (the last one shows verification being blocked)
- Run traces in the UI for every stage
- Deployed frontend (Vercel) calling a separately deployed FastAPI backend

## 4. Current limitations

- **Narrow physical domain.** Only gear trains with external meshes: ratio, RPM and direction. No torque, loads, materials, efficiency or tolerances.
- **Single path only.** Branched, cyclic or disconnected topologies are rejected, not analyzed.
- **Redesign scope.** The autonomous redesign changes the two tooth counts of a fixed single-mesh (two-gear) system. Input RPM, topology and the constraint are fixed context.
- **SAM does not measure.** SAM detects components; tooth counts, shafts, meshes and RPM come from the user's confirmation.
- **Demo Scenarios are fixtures.** They exercise the pipeline with synthetic perception, not real images.
- **No persistence or accounts.** Each run is independent; the frontend round-trips the perception state between requests.
- **Muse Spark Open** is not integrated.

## 5. Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, Uvicorn, python-multipart, python-dotenv |
| AI | Meta Model API through the OpenAI Python SDK: Muse Spark (`muse-spark-1.3`, chat completions with tool calling) and SAM 3.1 (`sam-3.1`, Responses API) |
| Physics | Pure Python modules in `backend/app/physics/`, with no AI dependencies |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Testing | Pytest and httpx (backend), Node's built-in test runner (frontend helpers) |
| Deployment | Frontend on Vercel; backend includes a `Procfile` and a `/health` endpoint for platform health checks |

## 6. Repository structure

```
backend/
  app/
    api/          FastAPI routers (experiments, forge, image_analysis, perception, pipeline)
    core/         backend/.env loading
    models/       Pydantic models: physics and perception
    perception/   evidence boundary builder and perception providers (SAM, fixtures)
    physics/      deterministic gears, train, topology, constraints, experiments
    sam/          SAM 3.1 client and output parser
    services/     Meta Model client, Muse orchestration, autonomous redesign, pipeline
  scripts/        manual connection checks for the Meta Model API and SAM
  tests/          pytest suite
frontend/
  app/            Next.js page and layout
  components/     workstation panels, overlays, traces, redesign panel
  lib/            API client, types and helpers (with tests)
docs/             original architecture and hackathon notes
```

## 7. API

All routes are under `/api/v1`, except `/health`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check (no credentials or network) |
| POST | `/api/v1/image-analysis/analyze` | Upload an image (multipart `image`, optional `prompt`); SAM 3.1 detections and missing information |
| POST | `/api/v1/image-analysis/confirm` | Perception state plus user confirmation → evidence boundary → deterministic physics |
| POST | `/api/v1/forge/autonomous-redesign` | `starting_train` and `objective_max_output_rpm` → bounded Muse Spark redesign loop |
| POST | `/api/v1/forge/analyze` | Objective and system data → Muse Spark analysis with physics tool calls |
| POST | `/api/v1/pipeline/run-fixture` | Full pipeline on a demo perception fixture |
| POST | `/api/v1/perception/build-physical-system` | Evidence boundary only: perception → `PhysicalSystem` or structured issues |
| POST | `/api/v1/experiments/gear-train` | Deterministic experiment on a gear train |
| POST | `/api/v1/experiments/physical-system` | Compile a `PhysicalSystem` topology and run the experiment |

Interactive docs are available at `http://localhost:8000/docs` when the backend is running.

## 8. Running locally

### Backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example backend/.env       # then set MODEL_API_KEY
cd backend
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. Without `MODEL_API_KEY`, everything that does not call Meta still works: `/health`, the deterministic experiments, the evidence boundary and the Demo Scenarios pipeline.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local         # optional; defaults to http://localhost:8000
npm run dev
```

Open `http://localhost:3000`.

### Environment variables

Never commit real values. `backend/.env` is loaded automatically and never overrides variables already set in the shell.

| Variable | Where | Purpose |
| --- | --- | --- |
| `MODEL_API_KEY` | backend | Single Meta Model API key, used for both Muse Spark and SAM 3.1. Required only for Meta calls. |
| `FORGE_CORS_ORIGINS` | backend | Comma-separated allowed browser origins. Defaults to `http://localhost:3000,http://127.0.0.1:3000`; never `*`. |
| `NEXT_PUBLIC_FORGE_API_URL` | frontend | Backend base URL. Defaults to `http://localhost:8000`. Public by design: the frontend holds no secrets. |

The Meta base URL (`https://api.meta.ai/v1`) and model names are defaults in `backend/app/services/meta_model.py` and `backend/app/sam/client.py`. The `APP_ENV`, `BACKEND_HOST` and `BACKEND_PORT` entries in `.env.example` are placeholders not currently read by the code.

## 9. Tests

```bash
# backend: runs fully offline, Meta clients are replaced by fakes
cd backend
pytest

# frontend helpers, lint and production build
cd frontend
npm test
npm run lint
npm run build
```

The backend suite never calls the Meta Model API and does not need `MODEL_API_KEY`. `backend/scripts/meta_connection_check.py` and `backend/scripts/sam_connection_check.py` are manual checks for a real connection.

## 10. Design principles

- **The AI chooses what to test, never the result.** Physical numbers only come from named Python tools executed by the backend. Model text is never accepted as a measurement.
- **Confidence is metadata, not verification.** Only `confirmed` values cross the evidence boundary.
- **Bounded agents.** Fixed tools, fixed limits on attempts and tool calls, explicit failure statuses instead of open-ended loops.
- **Injected model clients.** Muse Spark and SAM sit behind small protocols, so the whole suite runs deterministically without network access.

## 11. Hackathon context

FORGE was started from scratch for the Meta Global AI Developer Hackathon 2026 (Indie Developer track, "Push the Frontier"). The documents in [`docs/`](docs/) are the original architecture and scope notes written at the start of the event; this README describes the implemented system.

Meta's reference workshop [`meta-models/legal-agent-workshop`](https://github.com/meta-models/legal-agent-workshop) was reviewed for architectural patterns only (tool registry, verification inside the required tool call, bounded retries, single API credential). None of its domain code, prompts or data is used.
