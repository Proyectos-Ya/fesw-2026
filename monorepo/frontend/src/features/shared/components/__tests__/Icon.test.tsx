import { render } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Icon } from "../Icon";

describe("Icon", () => {
  it("renders registered icons by kebab-case name and aliases", () => {
    const names = [
      "sparkles",
      "building-2",
      "check-circle-2",
      "circle-check",
      "alert-circle",
      "alert-triangle",
      "sliders",
      "bookmark-check",
      "calendar-clock",
    ];

    for (const name of names) {
      const { container, unmount } = render(<Icon name={name} />);
      expect(container.querySelector("svg")).not.toBeNull();
      unmount();
    }
  });

  it("returns null and warns in development for unknown icon names", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { container } = render(<Icon name="icono-inexistente" />);
    expect(container.querySelector("svg")).toBeNull();
    expect(warnSpy).toHaveBeenCalledWith('[Icon] Unknown lucide name: "icono-inexistente"');
    warnSpy.mockRestore();
  });
});
