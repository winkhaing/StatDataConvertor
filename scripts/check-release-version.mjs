import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const packageVersion = JSON.parse(
  readFileSync(join(projectRoot, "package.json"), "utf8"),
).version;
const tauriVersion = JSON.parse(
  readFileSync(join(projectRoot, "src-tauri", "tauri.conf.json"), "utf8"),
).version;

function tomlVersion(path) {
  const content = readFileSync(path, "utf8");
  const match = content.match(/^version\s*=\s*"([^"]+)"/m);
  if (!match) throw new Error(`No package version was found in ${path}.`);
  return match[1];
}

function constantVersion(path, name) {
  const content = readFileSync(path, "utf8");
  const match = content.match(
    new RegExp(`^${name}\\s*=\\s*["']([^"']+)["']`, "m"),
  );
  if (!match) throw new Error(`No ${name} version was found in ${path}.`);
  return match[1];
}

const versions = new Map([
  ["package.json", packageVersion],
  ["src-tauri/tauri.conf.json", tauriVersion],
  [
    "src-tauri/Cargo.toml",
    tomlVersion(join(projectRoot, "src-tauri", "Cargo.toml")),
  ],
  [
    "engine/pyproject.toml",
    tomlVersion(join(projectRoot, "engine", "pyproject.toml")),
  ],
  [
    "engine package",
    constantVersion(
      join(
        projectRoot,
        "engine",
        "src",
        "statdata_converter",
        "__init__.py",
      ),
      "__version__",
    ),
  ],
  [
    "JMP bridge",
    constantVersion(
      join(
        projectRoot,
        "bridges",
        "jmp",
        "src",
        "statdata_jmp_bridge.py",
      ),
      "BRIDGE_VERSION",
    ),
  ],
  [
    "SAS bridge",
    constantVersion(
      join(
        projectRoot,
        "bridges",
        "sas",
        "src",
        "statdata_sas_bridge.py",
      ),
      "BRIDGE_VERSION",
    ),
  ],
  [
    "Windows COM bridges",
    constantVersion(
      join(
        projectRoot,
        "bridges",
        "windows-com",
        "src",
        "statdata_windows_com_bridge.py",
      ),
      "BRIDGE_VERSION",
    ),
  ],
]);

const mismatches = [...versions].filter(
  ([, version]) => version !== packageVersion,
);
if (mismatches.length) {
  throw new Error(
    `Release versions disagree:\n${[...versions]
      .map(([path, version]) => `${path}: ${version}`)
      .join("\n")}`,
  );
}

const releaseTag = process.env.RELEASE_TAG;
if (releaseTag && releaseTag !== `v${packageVersion}`) {
  throw new Error(
    `Release tag ${releaseTag} does not match version v${packageVersion}.`,
  );
}

console.log(
  `Release version ${packageVersion} is consistent${
    releaseTag ? ` with tag ${releaseTag}` : ""
  }.`,
);
