import { useMemo, useState } from "react";
import { validateDataset } from "../lib/engine";
import {
  chooseDirectory,
  chooseInput,
  detectFormat,
  fileName,
} from "../lib/files";
import type {
  FormatCapability,
  ValidationResult,
} from "../types";
import { FormatSelect } from "./FormatSelect";
import { ValidationResultView } from "./ValidationResultView";

interface ValidationWorkspaceProps {
  formats: FormatCapability[];
}

export function ValidationWorkspace({
  formats,
}: ValidationWorkspaceProps) {
  const [inputPath, setInputPath] = useState("");
  const [inputFormat, setInputFormat] = useState("");
  const [targetFormat, setTargetFormat] = useState("");
  const [artifactDirectory, setArtifactDirectory] = useState("");
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const roundTripFormats = useMemo(
    () => formats.filter((format) => format.can_read && format.can_write),
    [formats],
  );

  async function handleChooseInput() {
    setError("");
    const path = await chooseInput(formats);
    if (!path) return;
    const detected = detectFormat(path, formats);
    setInputPath(path);
    setInputFormat(detected?.id || "");
    if (!targetFormat) {
      const target = roundTripFormats.find(
        (format) => format.id !== detected?.id,
      );
      setTargetFormat(target?.id || roundTripFormats[0]?.id || "");
    }
  }

  async function handleChooseDirectory() {
    const path = await chooseDirectory();
    if (path) setArtifactDirectory(path);
  }

  async function handleValidate() {
    if (!inputPath || !inputFormat || !targetFormat) return;
    setRunning(true);
    setError("");
    try {
      const validation = await validateDataset({
        inputPath,
        inputFormat,
        targetFormat,
        artifactDirectory: artifactDirectory || undefined,
      });
      setResult(validation);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The round-trip validation could not finish.",
      );
    } finally {
      setRunning(false);
    }
  }

  function reset() {
    setInputPath("");
    setInputFormat("");
    setTargetFormat("");
    setArtifactDirectory("");
    setResult(null);
    setError("");
  }

  if (result) {
    return (
      <ValidationResultView
        result={result}
        formats={formats}
        onReset={reset}
      />
    );
  }

  const ready = Boolean(inputPath && inputFormat && targetFormat) && !running;
  return (
    <section className="converter-card validation-card">
      <div className="step">
        <div className="step-number">1</div>
        <div className="step-body">
          <div className="step-title">
            <div>
              <h2>Choose a trusted source file</h2>
              <p>The source becomes the baseline for the comparison.</p>
            </div>
          </div>
          <button className="file-drop" onClick={handleChooseInput}>
            <span className="file-icon" aria-hidden="true">
              ↑
            </span>
            {inputPath ? (
              <span className="file-selected">
                <strong>{fileName(inputPath)}</strong>
                <small>{inputPath}</small>
              </span>
            ) : (
              <span>
                <strong>Choose a validation fixture</strong>
                <small>Use a file created by the source application</small>
              </span>
            )}
          </button>
          <FormatSelect
            formats={formats}
            value={inputFormat}
            direction="input"
            onChange={setInputFormat}
          />
        </div>
      </div>

      <div className="step-divider">
        <span>↻</span>
      </div>

      <div className="step">
        <div className="step-number">2</div>
        <div className="step-body">
          <div className="step-title">
            <div>
              <h2>Select the round-trip format</h2>
              <p>
                The engine writes this format, reads it back, then compares every
                value and supported metadata field.
              </p>
            </div>
          </div>
          <FormatSelect
            formats={roundTripFormats}
            value={targetFormat}
            direction="output"
            onChange={setTargetFormat}
          />
          <button
            className="artifact-directory"
            onClick={handleChooseDirectory}
          >
            <span>
              {artifactDirectory
                ? "Validation folder selected"
                : "Validation evidence folder"}
            </span>
            <strong>
              {artifactDirectory || "Default: beside the source file"}
            </strong>
          </button>
        </div>
      </div>

      {error ? (
        <div className="error-message" role="alert">
          <strong>Validation could not finish</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="converter-footer">
        <div className="report-promise">
          <span aria-hidden="true">✓</span>
          The generated file, conversion report, and comparison evidence are
          retained.
        </div>
        <button
          className="button button--primary"
          disabled={!ready}
          onClick={handleValidate}
        >
          {running ? "Validating…" : "Run round-trip test"}
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </section>
  );
}
