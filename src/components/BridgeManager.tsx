import { useState } from "react";
import {
  auditCertification,
  getCapabilities,
  installLocalBridge,
} from "../lib/engine";
import {
  chooseBridgeManifest,
  chooseCertificationManifest,
} from "../lib/files";
import type {
  CapabilityResponse,
  CertificationAuditResult,
  DirectionCertification,
} from "../types";

interface BridgeManagerProps {
  capabilities: CapabilityResponse;
  onCapabilities: (value: CapabilityResponse) => void;
}

export function BridgeManager({
  capabilities,
  onCapabilities,
}: BridgeManagerProps) {
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [audit, setAudit] = useState<CertificationAuditResult | null>(null);

  async function refresh() {
    setWorking(true);
    setError("");
    try {
      onCapabilities(await getCapabilities());
      setMessage("Local software and bridge checks are up to date.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The local checks could not be refreshed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function addBridge() {
    setError("");
    setMessage("");
    const manifestPath = await chooseBridgeManifest();
    if (!manifestPath) return;
    setWorking(true);
    try {
      const result = await installLocalBridge(manifestPath);
      onCapabilities(result.capabilities);
      setMessage(
        result.bridge.available
          ? `${result.name} is installed and ready.`
          : `${result.name} is installed. Its required vendor software was not ready, so conversion remains disabled.`,
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The bridge could not be installed.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function auditEvidence() {
    setError("");
    setMessage("");
    setAudit(null);
    const manifestPath = await chooseCertificationManifest();
    if (!manifestPath) return;
    setWorking(true);
    try {
      setAudit(await auditCertification(manifestPath));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The certification evidence could not be audited.",
      );
    } finally {
      setWorking(false);
    }
  }

  function certificationLabel(value: DirectionCertification) {
    if (value.certified) return "Vendor verified";
    if (value.state === "fixture_tested") return "Fixture tested";
    return "Pending";
  }

  return (
    <section className="bridge-manager">
      <div className="bridge-manager__actions">
        <div>
          <p className="eyebrow">Optional local connections</p>
          <h2>Add capability without sending data away</h2>
          <p>
            A bridge lets this app use statistical software already installed on
            this computer. Install only a bridge bundle you trust.
          </p>
        </div>
        <div className="bridge-manager__buttons">
          <button
            className="button button--primary"
            disabled={working}
            onClick={addBridge}
          >
            {working ? "Checking…" : "Add local bridge"}
          </button>
          <button
            className="button button--secondary"
            disabled={working}
            onClick={refresh}
          >
            Refresh checks
          </button>
        </div>
      </div>

      {message ? (
        <div className="success-message" role="status">
          {message}
        </div>
      ) : null}
      {error ? (
        <div className="error-message" role="alert">
          <strong>Bridge setup could not finish</strong>
          <span>{error}</span>
        </div>
      ) : null}

      <div className="bridge-manager__grid">
        <div className="bridge-manager__panel">
          <div className="bridge-manager__heading">
            <div>
              <p className="eyebrow">Bridge bundles</p>
              <h3>Installed connections</h3>
            </div>
            <span>{capabilities.bridges.length}</span>
          </div>
          {capabilities.bridges.length ? (
            <div className="bridge-manager__list">
              {capabilities.bridges.map((bridge) => (
                <div className="bridge-manager__item" key={bridge.manifest_path}>
                  <span
                    className={
                      bridge.available
                        ? "status-dot"
                        : "status-dot status-dot--error"
                    }
                  />
                  <div>
                    <strong>{bridge.name}</strong>
                    <span className="bridge-manager__state">
                      {bridge.available ? "Ready" : "Needs attention"}
                    </span>
                    <p>{bridge.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="bridge-manager__empty">
              No optional bridges are installed. Open formats remain available
              without them.
            </p>
          )}
        </div>

        <div className="bridge-manager__panel">
          <div className="bridge-manager__heading">
            <div>
              <p className="eyebrow">Vendor software</p>
              <h3>Local runtime checks</h3>
            </div>
            <span>
              {
                capabilities.vendor_runtimes.filter((item) => item.detected)
                  .length
              }
              /{capabilities.vendor_runtimes.length}
            </span>
          </div>
          <div className="bridge-manager__list">
            {capabilities.vendor_runtimes.map((runtime) => (
              <div className="bridge-manager__item" key={runtime.id}>
                <span
                  className={
                    runtime.detected
                      ? "status-dot"
                      : "status-dot status-dot--muted"
                  }
                />
                <div>
                  <strong>{runtime.label}</strong>
                  <span className="bridge-manager__state">
                    {runtime.detected ? "Detected" : "Not detected"} ·{" "}
                    {runtime.automation}
                  </span>
                  <p>{runtime.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bridge-manager__safety">
        <strong>What installation does</strong>
        <p>
          The selected bundle is copied into this app’s local bridge folder. It
          cannot silently replace an existing bridge, and conversion is enabled
          only after its compatibility check succeeds.
        </p>
      </div>

      <div className="certification-panel">
        <div className="certification-panel__heading">
          <div>
            <p className="eyebrow">Certification registry</p>
            <h2>Evidence by format and direction</h2>
            <p>
              Fixture-tested is useful evidence, but only vendor-verified
              directions are certified.
            </p>
          </div>
          <button
            className="button button--secondary"
            disabled={working}
            onClick={auditEvidence}
          >
            Audit evidence package
          </button>
        </div>

        {audit ? (
          <div
            className={
              audit.status === "passed"
                ? "certification-audit certification-audit--passed"
                : "certification-audit certification-audit--failed"
            }
            role="status"
          >
            <strong>
              {audit.status === "passed"
                ? "Evidence audit passed"
                : "Evidence audit failed"}
            </strong>
            <span>
              {audit.format_id || "Unknown format"} · {audit.direction} ·{" "}
              {audit.claim.replaceAll("_", " ")}
            </span>
            <p>
              {audit.status === "passed"
                ? "This package is eligible for maintainer review; it has not been added to the certification registry automatically."
                : `${audit.summary.errors} required check(s) failed. Review the evidence manifest and generated issues.`}
            </p>
          </div>
        ) : null}

        <div className="certification-table" role="table">
          <div className="certification-table__header" role="row">
            <span role="columnheader">Format</span>
            <span role="columnheader">Read</span>
            <span role="columnheader">Write</span>
          </div>
          {capabilities.certifications.map((certification) => (
            <div
              className="certification-table__row"
              role="row"
              key={certification.format_id}
            >
              <div role="cell">
                <strong>{certification.family}</strong>
                <span>{certification.label}</span>
              </div>
              {[certification.read, certification.write].map(
                (direction, index) => (
                  <div role="cell" key={index === 0 ? "read" : "write"}>
                    <span
                      className={`certification-state certification-state--${direction.state}`}
                    >
                      {certificationLabel(direction)}
                    </span>
                    <p>{direction.detail}</p>
                    {direction.tested_versions.length ? (
                      <small>
                        Versions: {direction.tested_versions.join(", ")}
                      </small>
                    ) : null}
                  </div>
                ),
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
