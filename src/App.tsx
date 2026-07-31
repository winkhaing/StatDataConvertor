import { useEffect, useMemo, useState } from "react";
import { CapabilityMatrix } from "./components/CapabilityMatrix";
import { BridgeManager } from "./components/BridgeManager";
import { ConversionReportView } from "./components/ConversionReportView";
import { FormatSelect } from "./components/FormatSelect";
import { ValidationWorkspace } from "./components/ValidationWorkspace";
import { fallbackCapabilities } from "./data/fallbackCapabilities";
import { convertDataset, getCapabilities } from "./lib/engine";
import {
  chooseInput,
  chooseOutput,
  detectFormat,
  fileName,
} from "./lib/files";
import type {
  CapabilityResponse,
  ConversionResult,
  FormatCapability,
} from "./types";

type View = "convert" | "validate" | "formats" | "bridges";

const FAMILY_MARKS: Record<string, string> = {
  SAS: "S",
  "IBM SPSS": "P",
  Stata: "D",
  R: "R",
  Excel: "X",
  CSV: "C",
  JMP: "J",
  "JSON-stat": "{}",
  Minitab: "M",
  EViews: "E",
  Statistica: "T",
};

function App() {
  const [view, setView] = useState<View>("convert");
  const [capabilities, setCapabilities] = useState<CapabilityResponse>(
    fallbackCapabilities,
  );
  const [engineNote, setEngineNote] = useState("");
  const [inputPath, setInputPath] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [inputFormat, setInputFormat] = useState("");
  const [outputFormat, setOutputFormat] = useState("");
  const [stataVersion, setStataVersion] = useState("15");
  const [xportVersion, setXportVersion] = useState("8");
  const [temporalPolicy, setTemporalPolicy] = useState<"safe" | "compatible">(
    "safe",
  );
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [error, setError] = useState("");
  const [converting, setConverting] = useState(false);

  useEffect(() => {
    let active = true;
    getCapabilities()
      .then((value) => {
        if (active) {
          setCapabilities(value);
          setEngineNote("");
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setEngineNote(
            reason instanceof Error
              ? reason.message
              : "The local engine could not be reached.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const formats = capabilities.formats;
  const selectedOutput = useMemo(
    () => formats.find((format) => format.id === outputFormat),
    [formats, outputFormat],
  );
  const featuredFamilies = useMemo(() => {
    const seen = new Set<string>();
    return formats.filter((format) => {
      if (seen.has(format.family)) return false;
      seen.add(format.family);
      return true;
    });
  }, [formats]);

  async function handleChooseInput() {
    setError("");
    const path = await chooseInput(formats);
    if (!path) return;
    setInputPath(path);
    setOutputPath("");
    const detected = detectFormat(path, formats);
    if (detected) {
      setInputFormat(detected.id);
      if (!outputFormat || outputFormat === detected.id) {
        const next = formats.find(
          (format) => format.can_write && format.id !== detected.id,
        );
        setOutputFormat(next?.id || "");
      }
    }
  }

  async function handleChooseOutput() {
    if (!inputPath || !selectedOutput) return;
    const path = await chooseOutput(inputPath, selectedOutput);
    if (path) setOutputPath(path);
  }

  async function handleConvert() {
    if (!inputPath || !outputPath || !inputFormat || !outputFormat) return;
    setConverting(true);
    setError("");
    try {
      const outputOptions: Record<string, unknown> = {
        temporal_policy: temporalPolicy,
      };
      if (outputFormat === "stata") {
        outputOptions.stata_version = Number(stataVersion);
      } else if (outputFormat === "sas_xport") {
        outputOptions.xport_version = Number(xportVersion);
      }
      const conversion = await convertDataset({
        inputPath,
        outputPath,
        inputFormat,
        outputFormat,
        outputOptions,
      });
      setResult(conversion);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "The conversion failed.",
      );
    } finally {
      setConverting(false);
    }
  }

  function reset() {
    setInputPath("");
    setOutputPath("");
    setInputFormat("");
    setOutputFormat("");
    setStataVersion("15");
    setXportVersion("8");
    setTemporalPolicy("safe");
    setResult(null);
    setError("");
  }

  const ready =
    Boolean(inputPath) &&
    Boolean(outputPath) &&
    Boolean(inputFormat) &&
    Boolean(outputFormat) &&
    !converting;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => setView("convert")}>
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          <span>
            <strong>StatData</strong>
            <small>Converter</small>
          </span>
        </button>

        <nav aria-label="Primary">
          <button
            className={view === "convert" ? "nav-item nav-item--active" : "nav-item"}
            onClick={() => setView("convert")}
          >
            <span aria-hidden="true">⇄</span>
            Convert
          </button>
          <button
            className={view === "validate" ? "nav-item nav-item--active" : "nav-item"}
            onClick={() => setView("validate")}
          >
            <span aria-hidden="true">◎</span>
            Validate
          </button>
          <button
            className={view === "formats" ? "nav-item nav-item--active" : "nav-item"}
            onClick={() => setView("formats")}
          >
            <span aria-hidden="true">▦</span>
            Formats
          </button>
          <button
            className={view === "bridges" ? "nav-item nav-item--active" : "nav-item"}
            onClick={() => setView("bridges")}
          >
            <span aria-hidden="true">⌁</span>
            Vendor bridges
          </button>
        </nav>

        <div className="privacy-card">
          <span className="privacy-icon" aria-hidden="true">
            ⌂
          </span>
          <div>
            <strong>Private by design</strong>
            <p>Your data stays on this computer.</p>
          </div>
        </div>
        <div className="engine-version">
          <span className="status-dot" />
          Engine {capabilities.engine_version}
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div className="local-badge">
            <span aria-hidden="true">●</span>
            100% local processing
          </div>
          <button className="text-button" onClick={() => setView("formats")}>
            View format support
          </button>
        </header>

        {view === "bridges" ? (
          <div className="page page--wide">
            <div className="page-title">
              <p className="eyebrow">Vendor bridges</p>
              <h1>Connect trusted software already on this computer</h1>
              <p>
                Optional bridges add native vendor formats while all processing
                stays local. Installed does not mean verified: each bridge must
                pass its runtime check before it can convert.
              </p>
            </div>
            <BridgeManager
              capabilities={capabilities}
              onCapabilities={setCapabilities}
            />
          </div>
        ) : view === "formats" ? (
          <div className="page page--wide">
            <div className="page-title">
              <p className="eyebrow">Formats</p>
              <h1>Know exactly what will convert</h1>
              <p>
                Availability is detected from this installation. Experimental
                means implemented and testable—not yet certified lossless.
              </p>
            </div>
            <CapabilityMatrix
              formats={formats}
              bridges={capabilities.bridges}
              vendorRuntimes={capabilities.vendor_runtimes}
            />
          </div>
        ) : view === "validate" ? (
          <div className="page">
            <div className="hero">
              <p className="eyebrow">Evidence-based compatibility</p>
              <h1>Test a round trip before you trust a format.</h1>
              <p>
                Convert a known source into a target format and read it back.
                Values and metadata are compared separately, with reusable
                evidence saved locally.
              </p>
            </div>
            {engineNote ? <div className="notice">{engineNote}</div> : null}
            <ValidationWorkspace formats={formats} />
          </div>
        ) : (
          <div className="page">
            <div className="hero">
              <p className="eyebrow">Local statistical data conversion</p>
              <h1>Move data between tools—without losing the story inside it.</h1>
              <p>
                Convert values, labels, missing-value definitions, dates, and
                metadata. Every change is recorded in a transparent report.
              </p>
            </div>

            {engineNote ? <div className="notice">{engineNote}</div> : null}

            {result ? (
              <ConversionReportView result={result} onReset={reset} />
            ) : (
              <section className="converter-card">
                <div className="step">
                  <div className="step-number">1</div>
                  <div className="step-body">
                    <div className="step-title">
                      <div>
                        <h2>Choose your source file</h2>
                        <p>Formats are detected from the selected file.</p>
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
                          <strong>Choose a dataset</strong>
                          <small>Browse files on this computer</small>
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
                  <span>↓</span>
                </div>

                <div className="step">
                  <div className="step-number">2</div>
                  <div className="step-body">
                    <div className="step-title">
                      <div>
                        <h2>Choose the destination</h2>
                        <p>Only writable formats in this engine are shown.</p>
                      </div>
                    </div>
                    <div className="destination-grid">
                      <FormatSelect
                        formats={formats}
                        value={outputFormat}
                        direction="output"
                        onChange={(value) => {
                          setOutputFormat(value);
                          setOutputPath("");
                        }}
                      />
                      <button
                        className="output-path"
                        onClick={handleChooseOutput}
                        disabled={!inputPath || !selectedOutput}
                      >
                        <span>{outputPath ? "Output selected" : "Choose output file"}</span>
                        <strong>
                          {outputPath ? fileName(outputPath) : "Browse…"}
                        </strong>
                      </button>
                    </div>
                    {outputFormat === "stata" ? (
                      <label className="field format-option">
                        <span>Stata output generation</span>
                        <select
                          value={stataVersion}
                          onChange={(event) => setStataVersion(event.target.value)}
                        >
                          {[15, 14, 13, 12, 11, 10, 9, 8].map((version) => (
                            <option key={version} value={version}>
                              Stata {version}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    {outputFormat === "sas_xport" ? (
                      <label className="field format-option">
                        <span>SAS XPORT version</span>
                        <select
                          value={xportVersion}
                          onChange={(event) => setXportVersion(event.target.value)}
                        >
                          <option value="8">Version 8</option>
                          <option value="5">Version 5 (legacy compatibility)</option>
                        </select>
                      </label>
                    ) : null}
                    <label className="field format-option">
                      <span>Date &amp; time handling</span>
                      <select
                        value={temporalPolicy}
                        onChange={(event) =>
                          setTemporalPolicy(
                            event.target.value as "safe" | "compatible",
                          )
                        }
                      >
                        <option value="safe">
                          Stop if date or time meaning could change
                        </option>
                        <option value="compatible">
                          Continue and record every known change
                        </option>
                      </select>
                    </label>
                  </div>
                </div>

                {error ? (
                  <div className="error-message" role="alert">
                    <strong>Conversion could not finish</strong>
                    <span>{error}</span>
                  </div>
                ) : null}

                <div className="converter-footer">
                  <div className="report-promise">
                    <span aria-hidden="true">✓</span>
                    A fidelity report will be saved beside your converted file.
                  </div>
                  <button
                    className="button button--primary"
                    disabled={!ready}
                    onClick={handleConvert}
                  >
                    {converting ? "Converting…" : "Convert dataset"}
                    <span aria-hidden="true">→</span>
                  </button>
                </div>
              </section>
            )}

            <section className="format-strip" aria-label="Supported format families">
              <div>
                <p className="eyebrow">Built for real research workflows</p>
                <h2>One careful bridge between your statistical tools</h2>
              </div>
              <div className="format-marks">
                {featuredFamilies.map((format: FormatCapability) => (
                  <button
                    key={format.family}
                    onClick={() => setView("formats")}
                    title={format.family}
                  >
                    <span>{FAMILY_MARKS[format.family] || format.family[0]}</span>
                    {format.family}
                  </button>
                ))}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
