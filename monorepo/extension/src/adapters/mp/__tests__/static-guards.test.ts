import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("Static Security Guards (CA5, CA8)", () => {
  const adapterDir = path.resolve(__dirname, "..");
  const srcDir = path.resolve(__dirname, "../../..");

  const readSourceFiles = (dir: string): { file: string; content: string }[] => {
    const results: { file: string; content: string }[] = [];
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory() && entry.name !== "__tests__" && entry.name !== "__fixtures__") {
        results.push(...readSourceFiles(fullPath));
      } else if (entry.isFile() && (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx"))) {
        results.push({ file: fullPath, content: fs.readFileSync(fullPath, "utf-8") });
      }
    }
    return results;
  };

  it("CA8: ninguna parte del código de la extensión invoca .submit() ni .requestSubmit()", () => {
    const sources = readSourceFiles(path.join(srcDir, "adapters/mp"));
    sources.push(...readSourceFiles(path.join(srcDir, "entrypoints")));

    for (const { file, content } of sources) {
      expect(
        content.includes(".submit()"),
        `Archivo ${file} contiene llamada prohibida .submit()`
      ).toBe(false);

      expect(
        content.includes(".requestSubmit("),
        `Archivo ${file} contiene llamada prohibida .requestSubmit()`
      ).toBe(false);
    }
  });

  it("CA8: el adaptador de Mercado Público nunca realiza click en botones de envío o guardado", () => {
    const sources = readSourceFiles(path.join(srcDir, "adapters/mp"));

    for (const { file, content } of sources) {
      // Prohibir .click() sobre elementos de formulario
      const forbiddenClickPatterns = [
        /btnEnviar.*\.click\(\)/i,
        /btnGuardar.*\.click\(\)/i,
        /submit.*\.click\(\)/i,
        /declaracion.*\.click\(\)/i,
        /chkDeclaracion.*\.checked\s*=\s*true/i,
      ];

      for (const pattern of forbiddenClickPatterns) {
        expect(
          pattern.test(content),
          `Archivo ${file} infringe regla CA8 con patrón ${pattern}`
        ).toBe(false);
      }
    }
  });

  it("CA5: el adaptador jamás lee contraseñas ni campos password", () => {
    const sources = readSourceFiles(path.join(srcDir, "adapters/mp"));
    sources.push(...readSourceFiles(path.join(srcDir, "entrypoints")));

    for (const { file, content } of sources) {
      expect(
        content.includes('type="password"') || content.includes("type='password'"),
        `Archivo ${file} intenta seleccionar inputs de contraseña`
      ).toBe(false);

      expect(
        content.includes(".password"),
        `Archivo ${file} accede a propiedad password`
      ).toBe(false);
    }
  });

  it("CA5: el código de Mercado Público no accede a document.cookie", () => {
    const sources = readSourceFiles(path.join(srcDir, "adapters/mp"));
    const mpContent = fs.readFileSync(path.join(srcDir, "entrypoints/mp.content.ts"), "utf-8");

    for (const { file, content } of sources) {
      expect(
        content.includes("document.cookie"),
        `Archivo ${file} lee document.cookie`
      ).toBe(false);
    }

    expect(
      mpContent.includes("document.cookie"),
      "mp.content.ts lee document.cookie"
    ).toBe(false);
  });
});
