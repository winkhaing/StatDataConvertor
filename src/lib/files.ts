import { isTauri } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import type { FormatCapability } from "../types";

export function fileName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

export function detectFormat(
  path: string,
  formats: FormatCapability[],
): FormatCapability | undefined {
  const lower = path.toLowerCase();
  return formats.find((format) =>
    format.extensions.some((extension) =>
      lower.endsWith(extension.toLowerCase()),
    ),
  );
}

export async function chooseInput(
  formats: FormatCapability[],
): Promise<string | null> {
  if (!isTauri()) {
    return null;
  }
  const extensions = Array.from(
    new Set(
      formats
        .filter((format) => format.can_read)
        .flatMap((format) =>
          format.extensions.map((extension) => extension.replace(/^\./, "")),
        ),
    ),
  );
  const selection = await open({
    multiple: false,
    directory: false,
    title: "Choose a statistical dataset",
    filters: [{ name: "Statistical datasets", extensions }],
  });
  return typeof selection === "string" ? selection : null;
}

export async function chooseOutput(
  inputPath: string,
  format: FormatCapability,
): Promise<string | null> {
  if (!isTauri()) {
    return null;
  }
  const sourceName = fileName(inputPath);
  const sourceBase =
    sourceName.lastIndexOf(".") > 0
      ? sourceName.slice(0, sourceName.lastIndexOf("."))
      : sourceName;
  const extension = format.extensions[0] || ".dat";
  return save({
    title: `Save as ${format.label}`,
    defaultPath: `${sourceBase}${extension}`,
    filters: [
      {
        name: format.label,
        extensions: format.extensions.map((item) => item.replace(/^\./, "")),
      },
    ],
  });
}

export async function chooseDirectory(): Promise<string | null> {
  if (!isTauri()) {
    return null;
  }
  const selection = await open({
    multiple: false,
    directory: true,
    title: "Choose a folder for validation artifacts",
  });
  return typeof selection === "string" ? selection : null;
}

export async function chooseBridgeManifest(): Promise<string | null> {
  if (!isTauri()) {
    return null;
  }
  const selection = await open({
    multiple: false,
    directory: false,
    title: "Choose a trusted bridge manifest",
    filters: [{ name: "StatData bridge manifest", extensions: ["json"] }],
  });
  return typeof selection === "string" ? selection : null;
}

export async function chooseCertificationManifest(): Promise<string | null> {
  if (!isTauri()) {
    return null;
  }
  const selection = await open({
    multiple: false,
    directory: false,
    title: "Choose a certification evidence manifest",
    filters: [{ name: "Certification evidence", extensions: ["json"] }],
  });
  return typeof selection === "string" ? selection : null;
}
