"use client";

import { useState } from "react";

import { EngineeringTrace } from "@/components/EngineeringTrace";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Header } from "@/components/Header";
import { Panel } from "@/components/Panel";
import { PhysicalModelColumn } from "@/components/PhysicalModelColumn";
import { ScenarioSelector } from "@/components/ScenarioSelector";
import { VerifiedResultPanel } from "@/components/VerifiedResultPanel";
import { ForgeApiError, runFixturePipeline } from "@/lib/api";
import type { FixtureId, PhysicalPipelineResult } from "@/lib/forge-types";

export default function Home() {
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
    <div className="flex min-h-screen flex-col">
      <Header />

      <main className="mx-auto flex w-full max-w-[1500px] flex-1 flex-col gap-3 px-6 py-3">
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
      </main>

      <footer className="border-t border-forge-border px-6 py-1.5 text-center text-[10px] text-forge-text-dim">
        FORGE · deterministic physics evidence, verified by the backend — never computed
        in this browser.
      </footer>
    </div>
  );
}
