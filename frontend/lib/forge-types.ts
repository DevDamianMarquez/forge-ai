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
  // Nullable: matches backend/app/models/perception.py exactly. A SAM-only
  // perception result (before any user confirmation) has neither an
  // observed input shaft nor an observed input RPM -- a static image
  // carries no information about either. The fixture provider happens to
  // always supply both, which is why earlier code treated these as
  // non-null; that was never actually guaranteed by the backend model.
  input_shaft_id: ObservedValue<string> | null;
  input_rpm: ObservedValue<number> | null;
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

/**
 * Milestone 7A.2 real-image types. These mirror
 * backend/app/sam/models.py and backend/app/services/image_analysis.py
 * exactly -- captured from reading those files directly, not guessed.
 */

/**
 * One SAM segmentation's box, in the source image's pixel coordinate
 * space. ``width``/``height`` are the FULL SOURCE IMAGE's pixel
 * dimensions (not the box's own width/height) -- see
 * backend/app/sam/parser.py's worked example from Meta's own docs:
 * "x1=181;y1=365;x2=556;y2=486;w=1516;h=1600". The w/h values there are
 * far larger than the box's own corner coordinates, so they cannot be the
 * box's dimensions; x1/y1/x2/y2 are absolute pixel coordinates within an
 * image of size width x height. See lib/real-image-helpers.ts for the
 * conversion into on-screen percentages.
 */
export interface SAMBoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  height: number;
  confidence: number | null;
}

/**
 * Safe, SAM-specific visual detection geometry for one segmentation.
 * Deliberately separate from PerceivedGear (which stays provider-
 * independent and carries no geometry at all). ``id`` always equals the
 * PerceivedGear id built from the same SAM segmentation.
 */
export interface VisualDetection {
  id: string;
  frame_index: number;
  object_index: number;
  bounding_box: SAMBoundingBox;
  confidence: number | null;
  source: ObservationSource;
  status: ObservationStatus;
}

/** Response of POST /api/v1/image-analysis/analyze. */
export interface AnalyzeImageResult {
  perception: PerceptionResult;
  detections: VisualDetection[];
  build_result: PhysicalSystemBuildResult;
}

/** A shaft the USER explicitly confirms exists. */
export interface ShaftConfirmation {
  id: string;
  label?: string | null;
}

/**
 * One gear's user-confirmed physical facts. ``confirmed_exists`` and the
 * attribute fields (``teeth``/``shaft_id``) are independent: supplying an
 * attribute never implies existence is confirmed, and vice versa -- this
 * must match the backend's GearConfirmation contract exactly.
 */
export interface GearConfirmation {
  id: string;
  confirmed_exists: boolean;
  teeth?: number | null;
  shaft_id?: string | null;
}

/** A gear mesh the USER explicitly confirms exists between two gears. */
export interface MeshConfirmation {
  gear_a_id: string;
  gear_b_id: string;
}

/** The smallest explicit USER confirmation contract (sent to /confirm). */
export interface PhysicalConfirmation {
  shafts: ShaftConfirmation[];
  gears: GearConfirmation[];
  meshes: MeshConfirmation[];
  input_shaft_id?: string | null;
  input_rpm?: number | null;
  output_shaft_id?: string | null;
}

/** Response of POST /api/v1/image-analysis/confirm. */
export interface ConfirmAndVerifyResult {
  perception: PerceptionResult;
  build_result: PhysicalSystemBuildResult;
  experiment: PhysicalSystemExperimentResult | null;
}

/**
 * Milestone 7B.1/7B.2 autonomous redesign types. These mirror
 * backend/app/services/autonomous_redesign.py and
 * backend/app/api/forge.py's AutonomousRedesignRequest exactly -- captured
 * from reading those files directly, not guessed.
 */

/** The only two numbers Muse may choose (see MIN_TEETH/MAX_TEETH on the backend). */
export interface GearRedesignCandidate {
  input_teeth: number;
  output_teeth: number;
}

export type RedesignAttemptStatus =
  | "passed"
  | "failed"
  | "duplicate"
  | "invalid_response"
  | "unknown_tool"
  | "invalid_arguments";

/** One attempt's full, structured record. ``candidate``/``experiment`` are
 * null exactly when no valid, non-duplicate candidate was actually
 * evaluated by physics this attempt. */
export interface RedesignAttempt {
  attempt_number: number;
  candidate: GearRedesignCandidate | null;
  experiment: ExperimentResult | null;
  status: RedesignAttemptStatus;
  error: string | null;
}

export type RedesignStatus = "verified" | "exhausted" | "model_error";

export type RedesignTraceStage =
  | "objective_received"
  | "candidate_proposed"
  | "physics_evaluated"
  | "constraint_checked"
  | "evidence_returned"
  | "design_verified"
  | "attempts_exhausted"
  | "invalid_response"
  | "model_error";

/** One concise, structured action/evidence event -- never chain-of-thought.
 * ``status`` is a plain string on the backend ("ok" | "failed"), not an enum. */
export interface RedesignTraceEntry {
  stage: RedesignTraceStage;
  status: string;
  message: string;
  attempt_number: number | null;
}

/** Response of POST /api/v1/forge/autonomous-redesign. ``accepted_design``/
 * ``final_experiment`` are non-null only when ``status === "verified"``. */
export interface AutonomousRedesignResult {
  objective: string;
  status: RedesignStatus;
  attempts: RedesignAttempt[];
  accepted_design: GearRedesignCandidate | null;
  final_experiment: ExperimentResult | null;
  trace: RedesignTraceEntry[];
}

/** Request body for POST /api/v1/forge/autonomous-redesign. ``starting_train``
 * must describe exactly one transmission stage (a single external two-gear
 * mesh) -- the only topology the backend supports for this milestone. */
export interface AutonomousRedesignRequest {
  starting_train: GearTrain;
  objective_max_output_rpm: number;
}
