import type { FormatCapability, ValidationResult } from "../types";

interface ValidationResultViewProps {
  result: ValidationResult;
  formats: FormatCapability[];
  onReset: () => void;
}

function Verdict({
  passed,
  label,
}: {
  passed: boolean;
  label: string;
}) {
  return (
    <div className={passed ? "verdict verdict--pass" : "verdict verdict--attention"}>
      <span aria-hidden="true">{passed ? "✓" : "!"}</span>
      <div>
        <strong>{label}</strong>
        <small>{passed ? "Preserved" : "Review required"}</small>
      </div>
    </div>
  );
}

export function ValidationResultView({
  result,
  formats,
  onReset,
}: ValidationResultViewProps) {
  const target = formats.find((format) => format.id === result.target_format);
  return (
    <section className="report-panel validation-result" aria-live="polite">
      <div className="report-heading">
        <div className={result.data_equivalent ? "report-icon" : "report-icon report-icon--warning"}>
          {result.data_equivalent ? "✓" : "!"}
        </div>
        <div>
          <p className="eyebrow">Round-trip evidence</p>
          <h2>
            {result.data_equivalent
              ? "The table survived the round trip"
              : "The round trip changed the data"}
          </h2>
          <p>
            Source → {target?.label || result.target_format} → canonical
            comparison
          </p>
        </div>
      </div>

      <div className="validation-verdicts">
        <Verdict passed={result.data_equivalent} label="Data values" />
        <Verdict passed={result.metadata_equivalent} label="Metadata" />
        <Verdict passed={result.lossless} label="Lossless claim" />
      </div>

      <div className="report-summary">
        <div>
          <strong>{result.rows.toLocaleString()}</strong>
          <span>Rows checked</span>
        </div>
        <div>
          <strong>{result.columns.toLocaleString()}</strong>
          <span>Columns checked</span>
        </div>
        <div>
          <strong>{result.summary.data_issues}</strong>
          <span>Data issues</span>
        </div>
        <div>
          <strong>{result.summary.metadata_issues}</strong>
          <span>Metadata issues</span>
        </div>
      </div>

      {result.issues.length ? (
        <div className="change-list">
          {result.issues.map((issue, index) => (
            <div
              className={`change change--${issue.severity}`}
              key={`${issue.code}-${index}`}
            >
              <span className="change-icon" aria-hidden="true">
                {issue.severity === "error" ? "!" : "i"}
              </span>
              <div>
                <strong>{issue.code}</strong>
                <p>{issue.message}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-note">
          No data or metadata differences were detected.
        </p>
      )}

      <div className="report-footer">
        <p>
          Validation evidence
          <span>{result.validation_path}</span>
        </p>
        <button className="button button--secondary" onClick={onReset}>
          Validate another file
        </button>
      </div>
    </section>
  );
}
