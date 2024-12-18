import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { PAGES_GLOB_BASE_DIR_PATH_FROM_FRONTEND_ROOT } from "./constants.js";

// resolve current directory
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// directory where external MDX files are stored
const pagesGlobBasePath = path.resolve(__dirname, PAGES_GLOB_BASE_DIR_PATH_FROM_FRONTEND_ROOT);

// directory where MDX files are copied to
const targetDir = path.resolve(__dirname, "src/pages");

// recursive copy function
function copyDir(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else if (entry.isFile() && path.extname(entry.name) === ".mdx") {
      fs.copyFileSync(srcPath, destPath);
      console.log(`Copied: ${srcPath} -> ${destPath}`);
    }
  }
}

// copy MDX files
if (fs.existsSync(pagesGlobBasePath)) {
  copyDir(pagesGlobBasePath, targetDir);
  console.log("MDX files copied successfully.");
} else {
  throw new Error(`Source directory does not exist: ${pagesGlobBasePath}`);
}
