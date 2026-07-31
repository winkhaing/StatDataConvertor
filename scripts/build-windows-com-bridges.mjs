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

if (process.platform !== "win32") {
  throw new Error("Minitab and Statistica COM bridges must be built on Windows.");
}

const projectRoot = resolve(import.meta.dirname, "..");
const engineDir = join(projectRoot, "engine");
const bridgeDir = join(projectRoot, "bridges", "windows-com");
const sourceDir = join(bridgeDir, "src");
const buildDir = join(bridgeDir, ".build");
const workDir = join(bridgeDir, ".work");
const bundleDir = join(bridgeDir, "bundle");
const executableName = "statdata-windows-com-bridge.exe";
const builtBinary = join(buildDir, executableName);

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
    "--name",
    "statdata-windows-com-bridge",
    "--distpath",
    buildDir,
    "--workpath",
    workDir,
    "--specpath",
    workDir,
    "--add-data",
    `${join(sourceDir, "minitab_bridge.ps1")};.`,
    "--add-data",
    `${join(sourceDir, "statistica_bridge.ps1")};.`,
    join(sourceDir, "statdata_windows_com_bridge.py"),
  ],
  { cwd: bridgeDir, stdio: "inherit" },
);

if (!existsSync(builtBinary)) {
  throw new Error(`PyInstaller did not create ${builtBinary}`);
}

for (const [folder, template] of [
  ["minitab", "manifest.minitab.template.json"],
  ["statistica", "manifest.statistica.template.json"],
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
