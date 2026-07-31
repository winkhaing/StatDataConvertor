import type { ConversionResult } from "../types";

interface ConversionReportViewProps {
  result: ConversionResult;
  onReset: () => void;
}

export function ConversionReportView({
  result,
  onReset,
}: ConversionReportViewProps) {
  const { report } = result;
  const temporal = report.temporal ?? [];
  return (
    <section className="report-panel" aria-labelledby="report-title">
      <div className="report-heading">
        <div className="success-mark" aria-hidden="true">
          ✓
        </div>
        <div>
          <p className="eyebrow">Conversion complete</p>
          <h2 id="report-title">
            {report.rows.toLocaleString()} rows · {report.columns} columns
          </h2>
          <p className="muted">Saved to {result.output_path}</p>
        </div>
      </div>

      <div className="report-summary">
        <div>
          <strong>{report.summary.info}</strong>
          <span>Notes</span>
        </div>
        <div>
          <strong>{report.summary.warning}</strong>
          <span>Warnings</span>
        </div>
        <div>
          <strong>{report.summary.error}</strong>
          <span>Errors</span>
        </div>
        <div>
          <strong>{report.lossless ? "Yes" : "No"}</strong>
          <span>Lossless</span>
        </div>
      </div>

      {temporal.length > 0 ? (
        <section className="temporal-report" aria-labelledby="temporal-title">
          <div className="temporal-report__heading">
            <div>
              <p className="eyebrow">Date &amp; time safety</p>
              <h3 id="temporal-title">Temporal columns checked</h3>
            </div>
            <span>
              {report.summary.temporal_lossy} of {temporal.length} changed
            </span>
          </div>
          <div className="temporal-list">
            {temporal.map((entry) => (
              <article
                className={`temporal-entry temporal-entry--${entry.outcome}`}
                key={entry.column}
              >
                <div className="temporal-entry__title">
                  <strong>{entry.column}</strong>
                  <span>{entry.outcome}</span>
                </div>
                <p className="temporal-route">
                  {entry.source_kind} · {entry.source_precision}
                  {entry.source_timezone ? ` · ${entry.source_timezone}` : ""}
                  <span aria-hidden="true"> → </span>
                  {entry.destination_kind} · {entry.destination_precision}
                  {entry.destination_timezone
                    ? ` · ${entry.destination_timezone}`
                    : ""}
                </p>
                <p>{entry.message}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <div className="change-list">
        {report.changes.length === 0 ? (
          <p className="empty-note">No transformations or metadata loss detected.</p>
        ) : (
          report.changes.map((change, index) => (
            <article className={`change change--${change.severity}`} key={`${change.code}-${index}`}>
              <span className="change-icon" aria-hidden="true">
                {change.severity === "warning"
                  ? "!"
                  : change.severity === "error"
                    ? "×"
                    : "i"}
              </span>
              <div>
                <strong>{change.code.replaceAll(".", " · ")}</strong>
                <p>{change.message}</p>
              </div>
            </article>
          ))
        )}
      </div>

      <div className="report-footer">
        <p>
          Full report <span>{result.report_path}</span>
        </p>
        <button className="button button--secondary" onClick={onReset}>
          Convert another file
        </button>
      </div>
    </section>
  );
}
