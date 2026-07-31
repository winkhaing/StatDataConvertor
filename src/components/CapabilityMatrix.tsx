import type {
  BridgeStatus,
  FormatCapability,
  VendorRuntimeStatus,
} from "../types";

interface CapabilityMatrixProps {
  formats: FormatCapability[];
  bridges?: BridgeStatus[];
  vendorRuntimes?: VendorRuntimeStatus[];
}

function SupportMark({ supported }: { supported: boolean }) {
  return supported ? (
    <span className="support support--yes">Supported</span>
  ) : (
    <span className="support support--no">Not yet</span>
  );
}

export function CapabilityMatrix({
  formats,
  bridges = [],
  vendorRuntimes = [],
}: CapabilityMatrixProps) {
  return (
    <section className="matrix-card">
      <div className="matrix-intro">
        <div>
          <p className="eyebrow">Runtime capability matrix</p>
          <h2>Honest support, direction by direction</h2>
        </div>
        <p>
          This table reflects the engine installed on this computer. Vendor
          bridges remain disabled until their software is detected and verified.
        </p>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Format</th>
              <th>Types</th>
              <th>Read</th>
              <th>Write</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {formats.map((format) => (
              <tr key={format.id}>
                <td>
                  <strong>{format.family}</strong>
                  <span>{format.label}</span>
                </td>
                <td className="extensions">{format.extensions.join(" · ")}</td>
                <td>
                  <SupportMark supported={format.can_read} />
                </td>
                <td>
                  <SupportMark supported={format.can_write} />
                </td>
                <td>
                  <span className={`trust trust--${format.trust}`}>
                    {format.availability === "vendor_bridge"
                      ? "Vendor bridge"
                      : format.availability === "dependency_missing"
                        ? "Dependency missing"
                        : format.trust}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {bridges.length ? (
        <div className="bridge-list">
          <p className="eyebrow">Detected local bridges</p>
          {bridges.map((bridge) => (
            <div className="bridge-row" key={bridge.manifest_path}>
              <span
                className={
                  bridge.available
                    ? "status-dot"
                    : "status-dot status-dot--error"
                }
              />
              <div>
                <strong>
                  {bridge.name}
                  {bridge.version ? ` ${bridge.version}` : ""}
                </strong>
                <p>{bridge.detail}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {vendorRuntimes.length ? (
        <div className="bridge-list">
          <p className="eyebrow">Local vendor runtimes</p>
          {vendorRuntimes.map((runtime) => (
            <div className="bridge-row" key={runtime.id}>
              <span
                className={
                  runtime.detected
                    ? "status-dot"
                    : "status-dot status-dot--muted"
                }
              />
              <div>
                <strong>
                  {runtime.label}
                  {runtime.version ? ` ${runtime.version}` : ""}
                  {` · ${runtime.automation}`}
                </strong>
                <p>{runtime.detail}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
