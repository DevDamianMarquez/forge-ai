# FORGE — Demo Frontend

The first real FORGE demo UI: **AI proposes. Physics verifies.**

A single page that calls the FORGE backend's deterministic pipeline
(`POST /api/v1/pipeline/run-fixture`) and visualizes, stage by stage, how a
perceived gear system becomes a verified physical result — or gets refused
at the evidence boundary.

This frontend computes nothing physical itself. Every RPM, ratio,
direction, and confirmation status shown comes directly from the backend's
JSON response; the browser only formats and displays it.

## Current perception scenarios are synthetic fixtures

The three scenarios in the selector (`simple_gear_pair`, `compound_gear_train`,
`uncertain_gear_pair`) are **deterministic, hand-authored development
fixtures** served by the backend — not output from SAM, a vision model, or
any image analysis. They exist to prove the full
perception → evidence boundary → topology → physics pipeline while real
perception is not yet integrated. This scenario panel will later be
replaced by SAM-backed perception without changing anything else in this
app (the API shape stays the same).

## Running locally

```bash
cd frontend
npm install
npm run dev
```

Then open <http://localhost:3000>. The backend must be running separately
(see the root `README.md`) and must allow CORS from this origin — see
`FORGE_CORS_ORIGINS` in the root `.env.example`.

## Configuration

Copy `.env.example` to `.env.local` and adjust if your backend isn't on the
default port:

```bash
cp .env.example .env.local
```

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_FORGE_API_URL` | Base URL of the FORGE FastAPI backend | `http://localhost:8000` |

There is no secret frontend credential today — this variable is public
(`NEXT_PUBLIC_*`) because the browser calls the backend directly.

## Scripts

```bash
npm run dev     # local dev server
npm run build   # production build (also type-checks)
npm run start   # serve a production build
npm run lint    # ESLint
npm test        # a few pure-logic unit tests (Node's built-in test runner, no extra deps)
```

## Stack

Next.js (App Router) + React + TypeScript + Tailwind CSS. No state
management library, no charting library, no WebGL/Three.js, no generic
component kit — a handful of small, purpose-built components plus inline
SVG for the gear-train schematic.
