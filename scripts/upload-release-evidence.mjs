import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";

const projectRoot = resolve(import.meta.dirname, "..");
const packageJson = JSON.parse(
  readFileSync(join(projectRoot, "package.json"), "utf8"),
);
const directories = ["release-packages", "release-metadata"];
const files = directories.flatMap((name) => {
  const directory = join(projectRoot, name);
  if (!existsSync(directory)) return [];
  return readdirSync(directory)
    .map((file) => join(directory, file))
    .filter((path) => !path.endsWith(".DS_Store"));
});

if (!process.env.GITHUB_ACTIONS) {
  throw new Error("Release evidence can be uploaded only from GitHub Actions.");
}
if (!files.length) {
  throw new Error("No release evidence files were found.");
}

execFileSync(
  "gh",
  ["release", "upload", `v${packageJson.version}`, ...files, "--clobber"],
  { cwd: projectRoot, stdio: "inherit" },
);
