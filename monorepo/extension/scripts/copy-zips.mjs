// Copia los .zip de producción que genera `wxt zip` al frontend, que los sirve como
// descarga mientras la extensión no esté en las tiendas (CA2 de la HU-32).
import { copyFileSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkg = JSON.parse((await import("node:fs")).readFileSync(join(root, "package.json"), "utf-8"));
const output = join(root, ".output");
const target = join(root, "..", "frontend", "public", "extension");
mkdirSync(target, { recursive: true });

const pick = (suffix) => {
  const name = readdirSync(output).find((f) => f.endsWith(`-${pkg.version}-${suffix}.zip`));
  if (!name) throw new Error(`No se encontró el .zip ${suffix} ${pkg.version} en .output`);
  return join(output, name);
};

copyFileSync(pick("chrome"), join(target, "chiripa-chrome.zip"));
copyFileSync(pick("firefox"), join(target, "chiripa-firefox.zip"));
writeFileSync(join(target, "version.json"), `${JSON.stringify({ version: pkg.version }, null, 2)}\n`);
console.log(`Zips ${pkg.version} copiados a ${target}`);
