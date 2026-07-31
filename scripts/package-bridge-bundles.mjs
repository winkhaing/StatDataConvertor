import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const packageJson = JSON.parse(
  readFileSync(join(projectRoot, "package.json"), "utf8"),
);
const outputDir = join(projectRoot, "release-packages");
const platformId = `${process.platform}-${process.arch}`;
const extension = process.platform === "win32" ? "zip" : "tar.gz";
const output = join(
  outputDir,
  `statdata-vendor-bridges-${packageJson.version}-${platformId}.${extension}`,
);
const bundleRoots = [
  join(projectRoot, "bridges", "jmp", "bundle"),
  join(projectRoot, "bridges", "sas", "bundle"),
  join(projectRoot, "bridges", "windows-com", "bundle"),
].filter(existsSync);

if (!bundleRoots.length) {
  throw new Error("No bridge bundles are available to package.");
}

mkdirSync(outputDir, { recursive: true });
const relativeRoots = bundleRoots.map((path) => relative(projectRoot, path));
const arguments_ =
  process.platform === "win32"
    ? ["-a", "-c", "-f", output, ...relativeRoots]
    : ["-c", "-z", "-f", output, ...relativeRoots];
execFileSync("tar", arguments_, { cwd: projectRoot, stdio: "inherit" });
console.log(`Prepared ${output}`);
