import { invoke, isTauri } from "@tauri-apps/api/core";
import type {
  CapabilityResponse,
  BridgeDiagnostics,
  BridgeInstallResult,
  CertificationAuditResult,
  ConversionRequest,
  ConversionResult,
  ValidationRequest,
  ValidationResult,
} from "../types";
import { fallbackCapabilities } from "../data/fallbackCapabilities";

export async function getCapabilities(): Promise<CapabilityResponse> {
  if (!isTauri()) {
    return fallbackCapabilities;
  }
  return invoke<CapabilityResponse>("engine_capabilities");
}

export async function getBridgeDiagnostics(): Promise<BridgeDiagnostics> {
  if (!isTauri()) {
    return {
      bridge_directory: "Desktop app only",
      installed_bridges: fallbackCapabilities.bridges,
      vendor_runtimes: fallbackCapabilities.vendor_runtimes,
      summary: {
        installed: fallbackCapabilities.bridges.length,
        ready: fallbackCapabilities.bridges.filter((item) => item.available)
          .length,
        vendor_runtimes_detected:
          fallbackCapabilities.vendor_runtimes.filter((item) => item.detected)
            .length,
      },
    };
  }
  return invoke<BridgeDiagnostics>("bridge_diagnostics");
}

export async function installLocalBridge(
  manifestPath: string,
): Promise<BridgeInstallResult> {
  if (!isTauri()) {
    throw new Error("Local bridges can be installed only in the desktop app.");
  }
  return invoke<BridgeInstallResult>("install_bridge", {
    request: { manifestPath },
  });
}

export async function auditCertification(
  manifestPath: string,
): Promise<CertificationAuditResult> {
  if (!isTauri()) {
    throw new Error(
      "Certification evidence can be audited only in the desktop app.",
    );
  }
  return invoke<CertificationAuditResult>("audit_certification", {
    request: { manifestPath },
  });
}

export async function convertDataset(
  request: ConversionRequest,
): Promise<ConversionResult> {
  if (!isTauri()) {
    throw new Error(
      "Conversions run in the desktop app. Open this interface with Tauri to choose local files.",
    );
  }
  return invoke<ConversionResult>("convert_dataset", { request });
}

export async function validateDataset(
  request: ValidationRequest,
): Promise<ValidationResult> {
  if (!isTauri()) {
    throw new Error(
      "Round-trip validation runs in the desktop app with local files.",
    );
  }
  return invoke<ValidationResult>("validate_dataset", { request });
}
