import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ExpiredLinkNotice } from "../ExpiredLinkNotice";

describe("ExpiredLinkNotice", () => {
  it("explica que el enlace cumplió sus 7 días", () => {
    // Criterio 6: la página de "Enlace caducado".
    render(<ExpiredLinkNotice reason="caducado" />);

    expect(screen.getByRole("heading", { name: "Enlace caducado" })).toBeInTheDocument();
    expect(screen.getByText(/7 días/)).toBeInTheDocument();
  });

  it("si fue revocado lo dice", () => {
    render(<ExpiredLinkNotice reason="revocado" />);

    expect(screen.getByRole("heading", { name: "Enlace caducado" })).toBeInTheDocument();
    expect(screen.getByText(/revocó/)).toBeInTheDocument();
  });

  it("sin motivo conocido usa el mensaje de vencimiento", () => {
    render(<ExpiredLinkNotice reason={null} />);

    expect(screen.getByText(/7 días/)).toBeInTheDocument();
  });

  it("sugiere pedir un enlace nuevo", () => {
    render(<ExpiredLinkNotice reason="caducado" />);

    expect(screen.getByText(/pide un enlace nuevo/i)).toBeInTheDocument();
  });
});
