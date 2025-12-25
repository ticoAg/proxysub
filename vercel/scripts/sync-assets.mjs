import fs from "node:fs";
import path from "node:path";

const projectRoot = path.resolve(process.cwd());
const repoRoot = path.resolve(projectRoot, "..");

function copyFile(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

copyFile(path.join(repoRoot, "templates", "ryan.yaml"), path.join(projectRoot, "public", "templates", "ryan.yaml"));
