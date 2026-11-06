import { build } from "esbuild";
import { mkdir, copyFile, rm } from "node:fs/promises";
await rm("dist", { recursive: true, force: true });
await mkdir("dist");
await build({
  entryPoints: [
    "extension/background.ts",
    "extension/content.ts",
    "extension/options.ts",
  ],
  outdir: "dist",
  bundle: true,
  target: "chrome120",
  format: "iife",
});
for (const name of ["manifest.json", "options.html", "options.css"])
  await copyFile(`extension/${name}`, `dist/${name}`);
