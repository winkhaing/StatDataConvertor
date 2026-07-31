import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const platformId = `${process.platform}-${process.arch}`;
const manifestPath = join(
  projectRoot,
  "release-metadata",
  `${platformId}.json`,
);

if (!existsSync(manifestPath)) {
  throw new Error(`Release manifest does not exist: ${manifestPath}`);
}

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const failures = [];
for (const artifact of manifest.artifacts ?? []) {
  const path = join(projectRoot, artifact.path);
  if (!existsSync(path) || !statSync(path).isFile()) {
    failures.push(`${artifact.path}: missing`);
    continue;
  }
  const content = readFileSync(path);
  const actual = createHash("sha256").update(content).digest("hex");
  if (actual !== artifact.sha256) {
    failures.push(`${artifact.path}: SHA-256 mismatch`);
  } else if (content.length !== artifact.size_bytes) {
    failures.push(`${artifact.path}: size mismatch`);
  }
}

if (failures.length) {
  throw new Error(`Release verification failed:\n${failures.join("\n")}`);
}

console.log(
  `Verified ${manifest.artifacts.length} release files for ${platformId}.`,
);
