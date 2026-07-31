import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { join, relative, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const packageJson = JSON.parse(
  readFileSync(join(projectRoot, "package.json"), "utf8"),
);
const outputDir = join(projectRoot, "release-metadata");
const platformId = `${process.platform}-${process.arch}`;
const installerRoot = join(
  projectRoot,
  "src-tauri",
  "target",
  "release",
  "bundle",
);
const releasePackageRoot = join(projectRoot, "release-packages");
const installerExtensions = [
  ".dmg",
  ".AppImage",
  ".deb",
  ".rpm",
  ".msi",
  ".exe",
];

function filesBelow(root) {
  if (!existsSync(root)) return [];
  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => join(entry.parentPath, entry.name))
    .sort();
}

const distributionFiles = [
  ...filesBelow(installerRoot).filter((path) =>
    installerExtensions.some((extension) => path.endsWith(extension)),
  ),
  ...filesBelow(releasePackageRoot),
];

const artifacts = distributionFiles.map((path) => {
  const content = readFileSync(path);
  return {
    path: relative(projectRoot, path).replaceAll("\\", "/"),
    size_bytes: statSync(path).size,
    sha256: createHash("sha256").update(content).digest("hex"),
  };
});

if (!artifacts.length) {
  throw new Error("No release artifacts were found.");
}

mkdirSync(outputDir, { recursive: true });
const manifest = {
  schema_version: 1,
  product: "StatData Converter",
  version: packageJson.version,
  platform: process.platform,
  architecture: process.arch,
  build: {
    repository: process.env.GITHUB_REPOSITORY || null,
    commit: process.env.GITHUB_SHA || null,
    run_id: process.env.GITHUB_RUN_ID || null,
    signing_required: process.env.RELEASE_REQUIRE_SIGNING === "true",
  },
  artifacts,
};
writeFileSync(
  join(outputDir, `${platformId}.json`),
  `${JSON.stringify(manifest, null, 2)}\n`,
);
writeFileSync(
  join(outputDir, `SHA256SUMS-${platformId}.txt`),
  `${artifacts.map((item) => `${item.sha256}  ${item.path}`).join("\n")}\n`,
);
console.log(`Recorded ${artifacts.length} release files for ${platformId}.`);
