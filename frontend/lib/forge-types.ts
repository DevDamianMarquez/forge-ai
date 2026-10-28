/**
 * TypeScript mirrors of FORGE backend JSON shapes.
 *
 * These were captured directly from a live POST to
 * /api/v1/pipeline/run-fixture for simple_gear_pair, compound_gear_train,
 * and uncertain_gear_pair -- not guessed. Keep this file in sync with
 * backend/app/models/perception.py and backend/app/models/physics.py;
 * the frontend never recomputes any of these values itself.
 */

export type ObservationSource = "user" | "vision_model" | "reasoning_model" | "derived";

export type ObservationStatus = "observed" | "inferred" | "confirmed" | "rejected" | "unresolved";

export interface ObservedValue<T> {
  value: T;
  source: ObservationSource;
  confidence: number;
  status: ObservationStatus;
}

export interface PerceivedShaft {
  id: string;
  label: string | null;
  source: ObservationSource;
  confidence: number;
  status: ObservationStatus;
}

export interface PerceivedGear {
  id: string;
  label: string | null;
  source: ObservationSource;
  confidence: number;
  status: ObservationStatus;
  teeth: ObservedValue<number>;
  shaft_id: ObservedValue<string>;
}

export interface PerceivedGearMesh {
  gear_a_id: string;
  gear_b_id: string;
  source: ObservationSource;
  confidence: number;
  status: ObservationStatus;
}

export interface PerceptionResult {
  shafts: PerceivedShaft[];
  gears: PerceivedGear[];
  meshes: PerceivedGearMesh[];
  input_shaft_id: ObservedValue<string>;
  input_rpm: ObservedValue<number>;
  output_shaft_id: ObservedValue<string> | null;
  notes: string[];
}

export type PerceptionIssueCode =
  | "unconfirmed_value"
  | "missing_value"
  | "rejected_value"
  | "invalid_reference";

export interface PerceptionIssue {
  code: PerceptionIssueCode;
  message: string;
  component_id: string | null;
  field: string | null;
  status: ObservationStatus | null;
}

export interface Shaft {
  id: string;
  label: string | null;
}

export interface SystemGear {
  id: string;
  teeth: number;
  shaft_id: string;
  label: string | null;
}

export interface GearMesh {
  gear_a_id: string;
  gear_b_id: string;
}

export type ConstraintMetric = "output_rpm" | "gear_ratio";
export type ConstraintOperator = "lte" | "gte" | "lt" | "gt" | "eq";

export interface Constraint {
  name: string;
  metric: ConstraintMetric;
  operator: ConstraintOperator;
  value: number;
}

export interface PhysicalSystem {
  shafts: Shaft[];
  gears: SystemGear[];
  meshes: GearMesh[];
  input_shaft_id: string;
  input_rpm: number;
  output_shaft_id: string | null;
  constraints: Constraint[];
}

export interface PhysicalSystemBuildResult {
  physical_system: PhysicalSystem | null;
  accepted_observations: string[];
  unresolved_observations: string[];
  issues: PerceptionIssue[];
}

export interface Gear {
  id: string;
  teeth: number;
  label: string | null;
}

export interface GearConnection {
  driver: Gear;
  driven: Gear;
}

export interface GearTrain {
  input_rpm: number;
  input_direction: 1 | -1;
  connections: GearConnection[];
}

export interface CompiledTopology {
  input_shaft_id: string;
  output_shaft_id: string;
  shaft_path: string[];
  gear_meshes_used: GearMesh[];
  gear_train: GearTrain;
}

export type ExperimentStatus = "success" | "error";

export interface ConstraintResult {
  constraint: Constraint;
  actual_value: number;
  passed: boolean;
  message: string;
}

export interface ExperimentResult {
  tool: string;
  inputs: Record<string, unknown>;
  result: number | null;
  unit: string | null;
  status: ExperimentStatus;
  error: string | null;
  metrics: Record<string, number>;
  constraint_results: ConstraintResult[];
}

export interface PhysicalSystemExperimentResult {
  topology: CompiledTopology;
  experiment: ExperimentResult;
}

export type PipelineStage = "perception" | "model_build" | "topology" | "experiment";
export type PipelineStageStatus = "ok" | "refused";

export interface PipelineTraceEntry {
  stage: PipelineStage;
  status: PipelineStageStatus;
  message: string;
}

export type PipelineStatus = "completed" | "refused_at_model_build";

export interface PhysicalPipelineResult {
  status: PipelineStatus;
  perception: PerceptionResult;
  build_result: PhysicalSystemBuildResult;
  experiment: PhysicalSystemExperimentResult | null;
  trace: PipelineTraceEntry[];
}

export type FixtureId = "simple_gear_pair" | "compound_gear_train" | "uncertain_gear_pair";
