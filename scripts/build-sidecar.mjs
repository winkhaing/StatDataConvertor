import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const engineDir = join(projectRoot, "engine");
const outputDir = join(projectRoot, "src-tauri", "binaries");
const targetTriple = execFileSync("rustc", ["--print", "host-tuple"], {
  encoding: "utf8",
}).trim();
const extension = process.platform === "win32" ? ".exe" : "";
const builtBinary = join(engineDir, "dist", `statdata-engine${extension}`);
const targetBinary = join(
  outputDir,
  `statdata-engine-${targetTriple}${extension}`,
);
const macEntitlements = join(
  projectRoot,
  "src-tauri",
  "Entitlements.plist",
);
const macSigningArguments =
  process.platform === "darwin" && process.env.APPLE_SIGNING_IDENTITY
    ? ["--codesign-identity", process.env.APPLE_SIGNING_IDENTITY]
    : [];

execFileSync(
  "uv",
  [
    "run",
    "--project",
    engineDir,
    "--extra",
    "statistical",
    "--extra",
    "build",
    "pyinstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    ...macSigningArguments,
    "--exclude-module",
    "pytest",
    "--exclude-module",
    "pygments",
    "--exclude-module",
    "setuptools",
    "--name",
    "statdata-engine",
    join(engineDir, "sidecar.py"),
  ],
  { cwd: engineDir, stdio: "inherit" },
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
mkdirSync(outputDir, { recursive: true });
rmSync(targetBinary, { force: true });
copyFileSync(builtBinary, targetBinary);
console.log(`Prepared ${targetBinary}`);
