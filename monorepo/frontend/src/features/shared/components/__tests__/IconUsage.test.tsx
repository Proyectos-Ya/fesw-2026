import { readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Icon } from "../Icon";

/**
 * `Icon` only renders names present in its registry; an unknown name renders
 * nothing and fails silently in production. This test collects every literal
 * name passed to `<Icon name=...>` or to an `icon="..."` prop in the source and
 * checks that each one renders an SVG.
 */

const SRC_DIR = resolve(__dirname, "../../../..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "__tests__" ? [] : sourceFiles(path);
    return /\.tsx$/.test(entry.name) ? [path] : [];
  });
}

const STRING_LITERAL = /"([a-z0-9-]+)"/g;

function iconNamesIn(source: string): string[] {
  const names: string[] = [];
  // <Icon ... name="x" ...> or name={cond ? "a" : "b"}, also across lines.
  for (const [tag] of source.matchAll(/<Icon\b[^>]*?\/?>/g)) {
    const literal = tag.match(/\bname="([^"]+)"/);
    if (literal) names.push(literal[1]);
    const expression = tag.match(/\bname=\{([^}]*)\}/);
    if (expression) {
      // In a ternary only the branches are icon names, not the compared value.
      const branches = expression[1].includes("?")
        ? expression[1].slice(expression[1].indexOf("?"))
        : expression[1];
      for (const [, name] of branches.matchAll(STRING_LITERAL)) names.push(name);
    }
  }
  // Components that forward an `icon` prop to <Icon>, e.g. <Section icon="x">.
  for (const [, name] of source.matchAll(/\bicon="([a-z0-9-]+)"/g)) names.push(name);
  return names;
}

function iconUsages(): Map<string, string[]> {
  const usages = new Map<string, string[]>();
  for (const file of sourceFiles(SRC_DIR)) {
    for (const name of iconNamesIn(readFileSync(file, "utf8"))) {
      usages.set(name, [...(usages.get(name) ?? []), relative(SRC_DIR, file)]);
    }
  }
  return usages;
}

describe("Icon usages", () => {
  it("finds icon names in the source", () => {
    expect(iconUsages().size).toBeGreaterThan(20);
  });

  it("every icon name used in the source is registered", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const missing: string[] = [];
    for (const [name, files] of iconUsages()) {
      const { container, unmount } = render(<Icon name={name} />);
      if (!container.querySelector("svg")) missing.push(`${name} (${[...new Set(files)].join(", ")})`);
      unmount();
    }
    warnSpy.mockRestore();
    expect(missing).toEqual([]);
  });
});
