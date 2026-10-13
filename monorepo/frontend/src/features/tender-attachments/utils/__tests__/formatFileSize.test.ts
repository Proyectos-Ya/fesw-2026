import { describe, expect, it } from "vitest";

import { formatFileSize } from "../formatFileSize";

describe("formatFileSize", () => {
  it.each([
    [500, "500 B"],
    [2048, "2.0 KB"],
    [1572864, "1.5 MB"],
  ])("%d bytes se muestran como %s", (bytes, esperado) => {
    expect(formatFileSize(bytes)).toBe(esperado);
  });
});
