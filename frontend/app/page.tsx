"use client";

import { useEffect, useRef, useState } from "react";

import { DetectionOverlay } from "@/components/DetectionOverlay";
import { EngineeringTrace } from "@/components/EngineeringTrace";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Header } from "@/components/Header";
import { ImageUpload } from "@/components/ImageUpload";
import { ModeTabs, type WorkflowMode } from "@/components/ModeTabs";
import { Panel } from "@/components/Panel";
import { PhysicalModelColumn } from "@/components/PhysicalModelColumn";
import { RealImageConfirmationForm } from "@/components/RealImageConfirmationForm";
import { RealImageResultPanel } from "@/components/RealImageResultPanel";
import { RealImageTrace } from "@/components/RealImageTrace";
import { ScenarioSelector } from "@/components/ScenarioSelector";
import { VerifiedResultPanel } from "@/components/VerifiedResultPanel";
import { analyzeImage, confirmAndVerify, ForgeApiError, runFixturePipeline } from "@/lib/api";
import type {
  AnalyzeImageResult,
  ConfirmAndVerifyResult,
  FixtureId,
  PhysicalPipelineResult,
} from "@/lib/forge-types";
import {
  buildPhysicalConfirmation,
  buildRealImageTrace,
  initialGearForms,
  initialSystemForm,
  PreviewUrlTracker,
  type GearConfirmationFormState,
  type RealImagePhase,
  type SystemConfirmationFormState,
} from "@/lib/real-image-helpers";

export default function Home() {
  const [mode, setMode] = useState<WorkflowMode>("real_image");

  return (
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="mx-auto flex w-full max-w-[1500px] flex-1 flex-col gap-3 px-6 py-3">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-forge-text-dim">
            Engineering Workstation
          </p>
          <ModeTabs mode={mode} onChange={setMode} />
        </div>

        {mode === "real_image" ? <RealImageWorkflow /> : <DemoScenarioWorkflow />}
      </main>

      <footer className="border-t border-forge-border px-6 py-1.5 text-center text-[10px] text-forge-text-dim">
        FORGE · deterministic physics evidence, verified by the backend — never computed
        in this browser.
      </footer>
    </div>
  );
}

function DemoScenarioWorkflow() {
  const [selectedFixture, setSelectedFixture] = useState<FixtureId>("simple_gear_pair");
  const [result, setResult] = useState<PhysicalPipelineResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setIsRunning(true);
    setError(null);
    try {
      const pipelineResult = await runFixturePipeline(selectedFixture);
      setResult(pipelineResult);
    } catch (caught) {
      setResult(null);
      setError(
        caught instanceof ForgeApiError
          ? caught.message
          : "Could not reach the FORGE backend. Is it running?",
      );
    } finally {
      setIsRunning(false);
    }
  }

  function handleSelect(id: FixtureId) {
    setSelectedFixture(id);
    setResult(null);
    setError(null);
  }

  return (
    <>
      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[300px_1fr_420px]">
        <Panel title="Input / Scenario" eyebrow="01">
          <ScenarioSelector
            selected={selectedFixture}
            onSelect={handleSelect}
            onRun={handleRun}
            isRunning={isRunning}
          />
        </Panel>

        <Panel title="Autonomous Engineering Trace" eyebrow="02">
          <EngineeringTrace trace={result?.trace ?? null} />
        </Panel>

        <Panel
          title="Physical System Model"
          eyebrow="03"
          bodyClassName="p-3 max-h-[480px] overflow-y-auto forge-scrollbar"
        >
          <PhysicalModelColumn result={result} />
        </Panel>
      </div>

      <Panel title="Verified Result" eyebrow="04">
        <VerifiedResultPanel result={result} />
      </Panel>
    </>
  );
}

const ANALYZE_PROMPT = "gear";

interface RealImageWorkflowState {
  phase: RealImagePhase;
  previewUrl: string | null;
  fileName: string | null;
  analysis: AnalyzeImageResult | null;
  confirmResult: ConfirmAndVerifyResult | null;
  gearForms: GearConfirmationFormState[];
  systemForm: SystemConfirmationFormState;
  apiError: string | null;
}

const INITIAL_REAL_IMAGE_STATE: RealImageWorkflowState = {
  phase: "idle",
  previewUrl: null,
  fileName: null,
  analysis: null,
  confirmResult: null,
  gearForms: [],
  systemForm: initialSystemForm(),
  apiError: null,
};

function RealImageWorkflow() {
  const [state, setState] = useState<RealImageWorkflowState>(INITIAL_REAL_IMAGE_STATE);
  const previewUrlTracker = useRef(new PreviewUrlTracker());

  // Revoke whatever object URL is still live when this workflow unmounts
  // (e.g. the user switches to Demo Scenarios and never comes back). The
  // ref's identity never changes (it's created once via useRef), so
  // capturing it in a local is just to satisfy exhaustive-deps cleanly.
  useEffect(() => {
    const tracker = previewUrlTracker.current;
    return () => {
      const toRevoke = tracker.replace(null);
      if (toRevoke) URL.revokeObjectURL(toRevoke);
    };
  }, []);

  async function handleFileSelected(file: File) {
    const nextUrl = URL.createObjectURL(file);
    const toRevoke = previewUrlTracker.current.replace(nextUrl);
    if (toRevoke) URL.revokeObjectURL(toRevoke);

    setState({
      ...INITIAL_REAL_IMAGE_STATE,
      phase: "analyzing",
      previewUrl: nextUrl,
      fileName: file.name,
    });

    try {
      const analysis = await analyzeImage(file, ANALYZE_PROMPT);
      setState((previous) => ({
        ...previous,
        phase: "observed",
        analysis,
        gearForms: initialGearForms(analysis.detections.map((detection) => detection.id)),
        systemForm: initialSystemForm(),
      }));
    } catch (caught) {
      setState((previous) => ({
        ...previous,
        phase: "idle",
        apiError:
          caught instanceof ForgeApiError
            ? caught.message
            : "Could not reach the FORGE backend. Is it running?",
      }));
    }
  }

  function handleInvalidType(mimeType: string) {
    setState((previous) => ({
      ...previous,
      apiError: `Unsupported file type "${mimeType || "unknown"}". Upload a JPEG or PNG image.`,
    }));
  }

  function handleReset() {
    const toRevoke = previewUrlTracker.current.replace(null);
    if (toRevoke) URL.revokeObjectURL(toRevoke);
    setState(INITIAL_REAL_IMAGE_STATE);
  }

  function handleGearFormChange(id: string, patch: Partial<GearConfirmationFormState>) {
    setState((previous) => ({
      ...previous,
      gearForms: previous.gearForms.map((form) => (form.id === id ? { ...form, ...patch } : form)),
    }));
  }

  function handleSystemFormChange(patch: Partial<SystemConfirmationFormState>) {
    setState((previous) => ({ ...previous, systemForm: { ...previous.systemForm, ...patch } }));
  }

  async function handleVerify() {
    if (!state.analysis) return;
    setState((previous) => ({ ...previous, phase: "verifying", apiError: null }));
    try {
      const confirmation = buildPhysicalConfirmation(state.gearForms, state.systemForm);
      const confirmResult = await confirmAndVerify(state.analysis.perception, confirmation);
      setState((previous) => ({
        ...previous,
        confirmResult,
        phase: confirmResult.build_result.physical_system !== null ? "verified" : "incomplete",
      }));
    } catch (caught) {
      setState((previous) => ({
        ...previous,
        phase: "observed",
        apiError:
          caught instanceof ForgeApiError
            ? caught.message
            : "Could not reach the FORGE backend. Is it running?",
      }));
    }
  }

  const trace = buildRealImageTrace(state.analysis, state.confirmResult);
  const hasConfirmationStage =
    state.phase === "observed" || state.phase === "verifying" || state.phase === "incomplete" || state.phase === "verified";

  return (
    <>
      {state.apiError && <ErrorBanner message={state.apiError} />}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[320px_1fr_420px]">
        <Panel title="Mechanism Image" eyebrow="01">
          <ImageUpload
            phase={state.phase}
            fileName={state.fileName}
            onFileSelected={handleFileSelected}
            onInvalidType={handleInvalidType}
            onReset={handleReset}
          />
        </Panel>

        <Panel title="Visual Detections" eyebrow="02">
          {state.previewUrl ? (
            <div className="flex h-full flex-col gap-2">
              <DetectionOverlay previewUrl={state.previewUrl} detections={state.analysis?.detections ?? []} />
              {state.analysis && (
                <p className="text-[11px] leading-snug text-forge-text-muted">
                  Visual components detected — <span className="text-forge-warning">OBSERVED</span>, not
                  verified. Physical properties require confirmation before FORGE can run engineering
                  calculations.
                </p>
              )}
            </div>
          ) : (
            <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 text-center">
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-text-dim">
                No Image Yet
              </p>
              <p className="max-w-[240px] text-xs text-forge-text-muted">
                Upload a mechanism image to see SAM 3.1&apos;s visual detections here.
              </p>
            </div>
          )}
        </Panel>

        <Panel
          title="Evidence &amp; Confirmation"
          eyebrow="03"
          bodyClassName="p-3 max-h-[560px] overflow-y-auto forge-scrollbar"
        >
          {hasConfirmationStage && state.analysis ? (
            <RealImageConfirmationForm
              detections={state.analysis.detections}
              issues={(state.confirmResult ?? state.analysis).build_result.issues}
              gearForms={state.gearForms}
              onGearFormChange={handleGearFormChange}
              systemForm={state.systemForm}
              onSystemFormChange={handleSystemFormChange}
              onVerify={handleVerify}
              isVerifying={state.phase === "verifying"}
            />
          ) : (
            <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 text-center">
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-forge-text-dim">
                Awaiting Analysis
              </p>
              <p className="max-w-[220px] text-xs text-forge-text-muted">
                Confirmation fields appear once SAM has analyzed an image.
              </p>
            </div>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1.3fr]">
        <Panel title="Action / Evidence Trace" eyebrow="04">
          <RealImageTrace events={trace} />
        </Panel>

        <Panel title="Result" eyebrow="05">
          <RealImageResultPanel confirmResult={state.confirmResult} />
        </Panel>
      </div>
    </>
  );
}
