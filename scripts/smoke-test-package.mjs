import { execFileSync } from "node:child_process";
import {
  chmodSync,
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, relative, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const bundleRoot = join(
  projectRoot,
  "src-tauri",
  "target",
  "release",
  "bundle",
);
const metadataRoot = join(projectRoot, "release-metadata");
const packageVersion = JSON.parse(
  readFileSync(join(projectRoot, "package.json"), "utf8"),
).version;
const platformId = `${process.platform}-${process.arch}`;
const reportPath = join(metadataRoot, `smoke-${platformId}.json`);
const essentialFormats = new Set([
  "csv",
  "excel_xlsx",
  "jsonstat",
  "sas_data",
  "spss_data",
  "stata",
  "r_data",
  "jmp",
  "minitab",
  "eviews_wf2",
  "statistica",
]);
const report = {
  schema_version: 1,
  product: "StatData Converter",
  version: packageVersion,
  platform: process.platform,
  architecture: process.arch,
  status: "running",
  packages: [],
  error: null,
};

function filesBelow(root) {
  if (!existsSync(root)) return [];
  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => join(entry.parentPath, entry.name))
    .sort();
}

function oneFile(description, predicate) {
  const matches = filesBelow(bundleRoot).filter(predicate);
  if (matches.length !== 1) {
    throw new Error(
      `Expected one ${description}, found ${matches.length}: ${matches.join(", ")}`,
    );
  }
  return matches[0];
}

function oneEngine(root, executableName) {
  const matches = filesBelow(root).filter(
    (path) => basename(path) === executableName,
  );
  if (matches.length !== 1) {
    throw new Error(
      `Expected one packaged ${executableName}, found ${matches.length}.`,
    );
  }
  return matches[0];
}

function run(file, args, options = {}) {
  return execFileSync(file, args, {
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
    timeout: 240_000,
    ...options,
  });
}

function verifyEngine(
  enginePath,
  packageType,
  packagePath,
  packagedEnginePath,
  packagedApplicationPath,
) {
  const conversionRoot = mkdtempSync(join(tmpdir(), "statdata-convert-"));
  const inputPath = join(conversionRoot, "smoke.csv");
  const outputPath = join(conversionRoot, "smoke.xlsx");
  const conversionReportPath = join(conversionRoot, "conversion-report.json");
  writeFileSync(
    inputPath,
    "case_id,event_name,value\n1,baseline,12.5\n2,follow-up,18.25\n",
  );
  const requests = [
    { id: "capabilities", method: "capabilities" },
    {
      id: "conversion",
      method: "convert",
      params: {
        input_path: inputPath,
        output_path: outputPath,
        report_path: conversionReportPath,
      },
    },
  ];
  let capabilities;
  let conversion;
  try {
    const responses = run(enginePath, ["serve"], {
      input: `${requests.map((request) => JSON.stringify(request)).join("\n")}\n`,
    })
      .trim()
      .split(/\r?\n/)
      .map((line) => JSON.parse(line));
    const capabilityResponse = responses.find(
      (response) => response.id === "capabilities",
    );
    const conversionResponse = responses.find(
      (response) => response.id === "conversion",
    );
    if (capabilityResponse?.error) {
      throw new Error(`${packageType} capabilities failed: ${capabilityResponse.error}`);
    }
    if (conversionResponse?.error) {
      throw new Error(`${packageType} conversion failed: ${conversionResponse.error}`);
    }
    capabilities = capabilityResponse?.result;
    conversion = conversionResponse?.result;
    if (!capabilities || !conversion) {
      throw new Error(`${packageType} did not return both smoke-test responses.`);
    }
    if (!existsSync(outputPath) || !existsSync(conversionReportPath)) {
      throw new Error(`${packageType} did not create the XLSX output and report.`);
    }
    if (readFileSync(outputPath).subarray(0, 2).toString("ascii") !== "PK") {
      throw new Error(`${packageType} produced an invalid XLSX container.`);
    }
    const writtenReport = JSON.parse(
      readFileSync(conversionReportPath, "utf8"),
    );
    if (
      writtenReport.status !== "completed" ||
      writtenReport.rows !== 2 ||
      writtenReport.columns !== 3
    ) {
      throw new Error(`${packageType} conversion report failed its data checks.`);
    }
  } finally {
    rmSync(conversionRoot, { force: true, recursive: true });
  }
  if (capabilities.engine_version !== packageVersion) {
    throw new Error(
      `${packageType} engine version ${capabilities.engine_version} does not match ${packageVersion}.`,
    );
  }
  if (
    capabilities.privacy?.local_only !== true ||
    capabilities.privacy?.network_access !== false
  ) {
    throw new Error(`${packageType} changed the local-only privacy contract.`);
  }
  const formatIds = new Set(
    (capabilities.formats ?? []).map((format) => format.id),
  );
  const missingFormats = [...essentialFormats].filter(
    (formatId) => !formatIds.has(formatId),
  );
  if (missingFormats.length) {
    throw new Error(
      `${packageType} is missing essential formats: ${missingFormats.join(", ")}.`,
    );
  }
  if (!Array.isArray(capabilities.certifications)) {
    throw new Error(`${packageType} has no certification registry.`);
  }
  for (const certification of capabilities.certifications) {
    for (const direction of ["read", "write"]) {
      const status = certification[direction];
      if (status?.certified !== (status?.state === "vendor_verified")) {
        throw new Error(
          `${certification.format_id} ${direction} has an inconsistent certification claim.`,
        );
      }
    }
  }
  report.packages.push({
    type: packageType,
    path: relative(projectRoot, packagePath).replaceAll("\\", "/"),
    application_path: packagedApplicationPath,
    engine_path: packagedEnginePath,
    engine_version: capabilities.engine_version,
    format_count: capabilities.formats.length,
    certification_count: capabilities.certifications.length,
    privacy: capabilities.privacy,
    conversion: {
      input_format: conversion.report.input_format,
      output_format: conversion.report.output_format,
      rows: conversion.report.rows,
      columns: conversion.report.columns,
      status: conversion.report.status,
    },
  });
}

function smokeMacOS() {
  const dmg = oneFile(
    "versioned DMG",
    (path) => path.endsWith(".dmg") && path.includes(`_${packageVersion}_`),
  );
  const mountPoint = mkdtempSync(join(tmpdir(), "statdata-dmg-"));
  let mounted = false;
  try {
    run("hdiutil", [
      "attach",
      dmg,
      "-readonly",
      "-nobrowse",
      "-mountpoint",
      mountPoint,
    ]);
    mounted = true;
    const app = join(mountPoint, "StatData Converter.app");
    const application = join(
      app,
      "Contents",
      "MacOS",
      "statdata-converter-desktop",
    );
    const applicationsLink = join(mountPoint, "Applications");
    if (!existsSync(app)) {
      throw new Error("The DMG does not contain StatData Converter.app.");
    }
    if (
      !existsSync(applicationsLink) ||
      !lstatSync(applicationsLink).isSymbolicLink()
    ) {
      throw new Error("The DMG does not contain an Applications shortcut.");
    }
    if (!existsSync(application)) {
      throw new Error("The DMG does not contain the desktop executable.");
    }
    run("codesign", ["--verify", "--deep", "--strict", "--verbose=2", app]);
    verifyEngine(
      join(app, "Contents", "MacOS", "statdata-engine"),
      "dmg",
      dmg,
      "StatData Converter.app/Contents/MacOS/statdata-engine",
      "StatData Converter.app/Contents/MacOS/statdata-converter-desktop",
    );
  } finally {
    if (mounted) {
      run("hdiutil", ["detach", mountPoint]);
    }
    rmSync(mountPoint, { force: true, recursive: true });
  }
}

function smokeWindows() {
  const msi = oneFile(
    "versioned MSI",
    (path) => path.endsWith(".msi") && path.includes(packageVersion),
  );
  const extractionRoot = mkdtempSync(join(tmpdir(), "statdata-msi-"));
  try {
    run("msiexec.exe", [
      "/a",
      msi,
      "/qn",
      "/norestart",
      `TARGETDIR=${extractionRoot}`,
    ]);
    const engine = oneEngine(extractionRoot, "statdata-engine.exe");
    const application = oneEngine(
      extractionRoot,
      "statdata-converter-desktop.exe",
    );
    verifyEngine(
      engine,
      "msi",
      msi,
      relative(extractionRoot, engine).replaceAll("\\", "/"),
      relative(extractionRoot, application).replaceAll("\\", "/"),
    );
  } finally {
    rmSync(extractionRoot, { force: true, recursive: true });
  }
}

function smokeLinux() {
  const deb = oneFile(
    "versioned DEB",
    (path) => path.endsWith(".deb") && path.includes(packageVersion),
  );
  const debRoot = mkdtempSync(join(tmpdir(), "statdata-deb-"));
  try {
    run("dpkg-deb", ["-x", deb, debRoot]);
    const engine = oneEngine(debRoot, "statdata-engine");
    const application = oneEngine(debRoot, "statdata-converter-desktop");
    verifyEngine(
      engine,
      "deb",
      deb,
      relative(debRoot, engine).replaceAll("\\", "/"),
      relative(debRoot, application).replaceAll("\\", "/"),
    );
  } finally {
    rmSync(debRoot, { force: true, recursive: true });
  }

  const appImage = oneFile(
    "versioned AppImage",
    (path) => path.endsWith(".AppImage") && path.includes(packageVersion),
  );
  const appImageRoot = mkdtempSync(join(tmpdir(), "statdata-appimage-"));
  try {
    chmodSync(appImage, 0o755);
    run(appImage, ["--appimage-extract"], { cwd: appImageRoot });
    const extractedRoot = join(appImageRoot, "squashfs-root");
    const engine = oneEngine(extractedRoot, "statdata-engine");
    const application = oneEngine(
      extractedRoot,
      "statdata-converter-desktop",
    );
    verifyEngine(
      engine,
      "appimage",
      appImage,
      relative(extractedRoot, engine).replaceAll("\\", "/"),
      relative(extractedRoot, application).replaceAll("\\", "/"),
    );
  } finally {
    rmSync(appImageRoot, { force: true, recursive: true });
  }
}

mkdirSync(metadataRoot, { recursive: true });
try {
  if (process.platform === "darwin") {
    smokeMacOS();
  } else if (process.platform === "win32") {
    smokeWindows();
  } else if (process.platform === "linux") {
    smokeLinux();
  } else {
    throw new Error(`Unsupported smoke-test platform: ${process.platform}`);
  }
  report.status = "passed";
  console.log(
    `Packaged smoke tests passed for ${report.packages
      .map((item) => item.type)
      .join(" and ")}.`,
  );
} catch (error) {
  report.status = "failed";
  report.error = error instanceof Error ? error.message : String(error);
  throw error;
} finally {
  writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`);
  console.log(`Wrote ${reportPath}`);
}
