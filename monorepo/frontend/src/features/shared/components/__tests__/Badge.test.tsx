import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Badge } from "../Badge";

test("expone su tono en data-tone", () => {
  render(<Badge tone="warning">Segundo llamado</Badge>);
  expect(screen.getByText("Segundo llamado")).toHaveAttribute("data-tone", "warning");
});

test("sin tono es neutral", () => {
  render(<Badge>Sin dato</Badge>);
  expect(screen.getByText("Sin dato")).toHaveAttribute("data-tone", "neutral");
});
