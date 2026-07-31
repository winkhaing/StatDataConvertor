import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { basename, join, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const engineDir = join(projectRoot, "engine");
const bridgeDir = join(projectRoot, "bridges", "sas");
const source = join(bridgeDir, "src", "statdata_sas_bridge.py");
const buildDir = join(bridgeDir, ".build");
const workDir = join(bridgeDir, ".work");
const bundleDir = join(bridgeDir, "bundle");
const extension = process.platform === "win32" ? ".exe" : "";
const executableName = `statdata-sas-bridge${extension}`;
const builtBinary = join(buildDir, executableName);
const macEntitlements = join(
  projectRoot,
  "src-tauri",
  "Entitlements.plist",
);
const macSigningArguments =
  process.platform === "darwin" && process.env.APPLE_SIGNING_IDENTITY
    ? ["--codesign-identity", process.env.APPLE_SIGNING_IDENTITY]
    : [];

rmSync(buildDir, { force: true, recursive: true });
rmSync(workDir, { force: true, recursive: true });
rmSync(bundleDir, { force: true, recursive: true });
mkdirSync(buildDir, { recursive: true });
mkdirSync(bundleDir, { recursive: true });

execFileSync(
  "uv",
  [
    "run",
    "--project",
    engineDir,
    "--extra",
    "build",
    "pyinstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    ...macSigningArguments,
    "--name",
    "statdata-sas-bridge",
    "--distpath",
    buildDir,
    "--workpath",
    workDir,
    "--specpath",
    workDir,
    source,
  ],
  { cwd: bridgeDir, stdio: "inherit" },
);

if (!existsSync(builtBinary)) {
  throw new Error(`PyInstaller did not create ${builtBinary}`);
}
if (process.platform === "darwin") {
  execFileSync(
    "codesign",
    [
      "--force",
      "--sign",
      process.env.APPLE_SIGNING_IDENTITY || "-",
      "--options",
      "runtime",
      "--entitlements",
      macEntitlements,
      builtBinary,
    ],
    { stdio: "inherit" },
  );
}

for (const [folder, template] of [
  ["sas-data", "manifest.sas-data.template.json"],
  ["sas-cport", "manifest.cport.template.json"],
]) {
  const destination = join(bundleDir, folder);
  mkdirSync(destination, { recursive: true });
  copyFileSync(builtBinary, join(destination, executableName));
  copyFileSync(join(bridgeDir, "README.md"), join(destination, "README.md"));
  const manifest = readFileSync(join(bridgeDir, template), "utf8").replace(
    "__EXECUTABLE__",
    basename(executableName),
  );
  writeFileSync(join(destination, "bridge.json"), manifest);
}

console.log(`Prepared ${bundleDir}`);
