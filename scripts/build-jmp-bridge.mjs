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
const bridgeDir = join(projectRoot, "bridges", "jmp");
const sourceDir = join(bridgeDir, "src");
const buildDir = join(bridgeDir, ".build");
const workDir = join(bridgeDir, ".work");
const bundleDir = join(bridgeDir, "bundle");
const extension = process.platform === "win32" ? ".exe" : "";
const executableName = `statdata-jmp-bridge${extension}`;
const builtBinary = join(buildDir, executableName);
const dataSeparator = process.platform === "win32" ? ";" : ":";
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
    "statdata-jmp-bridge",
    "--distpath",
    buildDir,
    "--workpath",
    workDir,
    "--specpath",
    workDir,
    "--add-data",
    `${join(sourceDir, "jmp_bridge.jsl")}${dataSeparator}.`,
    join(sourceDir, "statdata_jmp_bridge.py"),
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

copyFileSync(builtBinary, join(bundleDir, executableName));
copyFileSync(join(bridgeDir, "README.md"), join(bundleDir, "README.md"));
const manifest = readFileSync(
  join(bridgeDir, "manifest.template.json"),
  "utf8",
).replace("__EXECUTABLE__", basename(executableName));
writeFileSync(join(bundleDir, "bridge.json"), manifest);
console.log(`Prepared ${bundleDir}`);
