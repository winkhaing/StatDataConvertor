export type Availability =
  | "available"
  | "dependency_missing"
  | "vendor_bridge"
  | "planned";

export interface FormatCapability {
  id: string;
  family: string;
  label: string;
  extensions: string[];
  can_read: boolean;
  can_write: boolean;
  trust: "verified" | "experimental" | "planned" | string;
  availability: Availability;
  detail: string;
  requires: string[];
}

export interface CapabilityResponse {
  engine_version: string;
  python_version: string;
  formats: FormatCapability[];
  bridges: BridgeStatus[];
  vendor_runtimes: VendorRuntimeStatus[];
  certifications: FormatCertification[];
  privacy: {
    local_only: boolean;
    network_access: boolean;
  };
}

export type CertificationState =
  | "pending"
  | "fixture_tested"
  | "vendor_verified";

export interface DirectionCertification {
  state: CertificationState;
  certified: boolean;
  tested_versions: string[];
  evidence_count: number;
  detail: string;
}

export interface FormatCertification {
  format_id: string;
  family: string;
  label: string;
  read: DirectionCertification;
  write: DirectionCertification;
}

export interface CertificationAuditIssue {
  severity: "warning" | "error";
  code: string;
  message: string;
}

export interface CertificationAuditResult {
  status: "passed" | "failed";
  eligible_for_registry_review: boolean;
  claim:
    | "lossless_fixture"
    | "verified_with_documented_changes"
    | "not_eligible";
  format_id: string;
  direction: "read" | "write" | "round_trip";
  manifest_path: string;
  fixture_path: string | null;
  validation_path: string | null;
  conversion_report_path: string | null;
  hashes: {
    fixture_sha256: string | null;
    validation_sha256: string | null;
    conversion_report_sha256: string | null;
  };
  data_equivalent: boolean;
  metadata_equivalent: boolean;
  lossless: boolean;
  issues: CertificationAuditIssue[];
  summary: {
    errors: number;
    warnings: number;
  };
}

export interface VendorRuntimeStatus {
  id: string;
  label: string;
  detected: boolean;
  executable: string | null;
  version: string | null;
  automation: string;
  detail: string;
}

export interface BridgeStatus {
  name: string;
  manifest_path: string;
  format_id: string | null;
  available: boolean;
  detail: string;
  version: string | null;
}

export interface BridgeDiagnostics {
  bridge_directory: string;
  installed_bridges: BridgeStatus[];
  vendor_runtimes: VendorRuntimeStatus[];
  summary: {
    installed: number;
    ready: number;
    vendor_runtimes_detected: number;
  };
}

export interface BridgeInstallResult {
  status: "installed";
  name: string;
  format_id: string;
  manifest_path: string;
  file_count: number;
  size_bytes: number;
  bridge: BridgeStatus;
  diagnostics: BridgeDiagnostics;
  capabilities: CapabilityResponse;
}

export interface ReportChange {
  severity: "info" | "warning" | "error";
  code: string;
  message: string;
  columns: string[];
}

export interface TemporalReportEntry {
  column: string;
  source_kind: string;
  source_precision: string;
  source_timezone: string | null;
  destination_kind: string;
  destination_precision: string;
  destination_timezone: string | null;
  outcome: "exact" | "lossy" | "unsupported" | "unverified";
  code: string;
  message: string;
}

export interface ConversionReport {
  input_path: string;
  output_path: string;
  input_format: string;
  output_format: string;
  started_at: string;
  finished_at: string;
  status: "completed" | "failed";
  rows: number;
  columns: number;
  changes: ReportChange[];
  temporal: TemporalReportEntry[];
  lossless: boolean;
  summary: {
    info: number;
    warning: number;
    error: number;
    temporal_columns: number;
    temporal_lossy: number;
  };
}

export interface ConversionResult {
  output_path: string;
  report_path: string;
  report: ConversionReport;
}

export interface ConversionRequest {
  inputPath: string;
  outputPath: string;
  inputFormat?: string;
  outputFormat?: string;
  inputOptions?: Record<string, unknown>;
  outputOptions?: Record<string, unknown>;
}

export interface ValidationIssue {
  severity: "info" | "warning" | "error";
  scope: "data" | "metadata" | "validation";
  code: string;
  message: string;
  column?: string;
  mismatch_count?: number;
  expected?: unknown;
  actual?: unknown;
  samples?: Array<{
    row: number;
    expected: unknown;
    actual: unknown;
  }>;
}

export interface ValidationResult {
  status: "passed" | "failed";
  input_path: string;
  input_format: string;
  target_format: string;
  artifact_path: string | null;
  conversion_report_path: string | null;
  validation_path: string;
  data_equivalent: boolean;
  metadata_equivalent: boolean;
  lossless: boolean;
  rows: number;
  columns: number;
  evidence: {
    schema_version: number;
    engine: Record<string, string>;
    platform: {
      system: string;
      release: string;
      machine: string;
    };
    source_adapter: Record<string, string>;
    target_adapter: Record<string, string>;
    bridges: BridgeStatus[];
    vendor_runtimes: VendorRuntimeStatus[];
    temporal: {
      source_columns: Array<Record<string, unknown>>;
      conversion_decisions: TemporalReportEntry[];
    };
  };
  issues: ValidationIssue[];
  summary: {
    data_issues: number;
    metadata_issues: number;
    conversion_warnings: number;
    conversion_errors: number;
  };
}

export interface ValidationRequest {
  inputPath: string;
  targetFormat: string;
  artifactDirectory?: string;
  inputFormat?: string;
  inputOptions?: Record<string, unknown>;
  outputOptions?: Record<string, unknown>;
}
