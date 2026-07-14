import { readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";

function* javascriptFiles(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) yield* javascriptFiles(path);
    else if (entry.isFile() && entry.name.endsWith(".js")) yield path;
  }
}

const files = [...javascriptFiles("functions"), join("assets", "download-pages.js")];
for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}
console.log(`JavaScript syntax OK: ${files.length} files`);
