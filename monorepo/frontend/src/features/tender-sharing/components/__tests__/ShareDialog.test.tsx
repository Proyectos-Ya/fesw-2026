import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as service from "../../services/sharingService";
import { ShareDialog } from "../ShareDialog";

vi.mock("../../services/sharingService", () => ({
  createShareLink: vi.fn(),
  listShareLinks: vi.fn(),
  revokeShareLink: vi.fn(),
}));

const CREADO = {
  id: "l-nuevo",
  url: "https://app.test/compartido/token-nuevo",
  created_at: "2026-09-28T15:00:00Z",
  expires_at: "2026-10-05T15:00:00Z",
};

const EXISTENTE = {
  id: "l-viejo",
  created_at: "2026-09-27T15:00:00Z",
  expires_at: "2026-10-04T15:00:00Z",
};

function abrir(onClose = vi.fn()) {
  render(<ShareDialog open tenderId="t-1" onClose={onClose} />);
  return onClose;
}

describe("ShareDialog", () => {
  beforeEach(() => {
    vi.mocked(service.listShareLinks).mockReset().mockResolvedValue([]);
    vi.mocked(service.createShareLink).mockReset().mockResolvedValue(CREADO);
    vi.mocked(service.revokeShareLink).mockReset().mockResolvedValue(undefined);
  });

  it("no muestra nada cerrado", () => {
    render(<ShareDialog open={false} tenderId="t-1" onClose={vi.fn()} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(service.listShareLinks).not.toHaveBeenCalled();
  });

  it("genera el enlace y lo muestra con su vencimiento a 7 días", async () => {
    // Criterio 1.
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: /generar enlace/i }));

    expect(await screen.findByDisplayValue(CREADO.url)).toBeInTheDocument();
    // 15:00 UTC es mediodía en Chile (horario de verano).
    expect(screen.getByText(/vigente hasta el 05 oct 2026, 12:00/i)).toBeInTheDocument();
    expect(service.createShareLink).toHaveBeenCalledWith("t-1");
  });

  it("copia el enlace al portapapeles", async () => {
    const user = userEvent.setup();
    abrir();
    await user.click(await screen.findByRole("button", { name: /generar enlace/i }));

    await user.click(await screen.findByRole("button", { name: /copiar enlace/i }));

    await expect(navigator.clipboard.readText()).resolves.toBe(CREADO.url);
    expect(screen.getByRole("button", { name: /copiado/i })).toBeInTheDocument();
  });

  it("avisa que la URL completa solo se ve ahora", async () => {
    const user = userEvent.setup();
    abrir();

    await user.click(await screen.findByRole("button", { name: /generar enlace/i }));

    expect(await screen.findByText(/no se vuelve a mostrar/i)).toBeInTheDocument();
  });

  it("lista los enlaces vigentes", async () => {
    vi.mocked(service.listShareLinks).mockResolvedValue([EXISTENTE]);
    abrir();

    const lista = await screen.findByRole("list", { name: /enlaces vigentes/i });

    expect(within(lista).getByText(/vence el 04 oct 2026, 12:00/i)).toBeInTheDocument();
    expect(service.listShareLinks).toHaveBeenCalledWith("t-1");
  });

  it("el enlace recién generado se suma a la lista", async () => {
    const user = userEvent.setup();
    vi.mocked(service.listShareLinks).mockResolvedValue([EXISTENTE]);
    abrir();

    await user.click(await screen.findByRole("button", { name: /generar enlace/i }));

    const lista = await screen.findByRole("list", { name: /enlaces vigentes/i });
    await waitFor(() => expect(within(lista).getAllByRole("listitem")).toHaveLength(2));
  });

  it("revoca un enlace tras confirmar y lo quita de la lista", async () => {
    // Criterio 7.
    const user = userEvent.setup();
    vi.mocked(service.listShareLinks).mockResolvedValue([EXISTENTE]);
    abrir();
    const lista = await screen.findByRole("list", { name: /enlaces vigentes/i });

    await user.click(within(lista).getByRole("button", { name: /^revocar/i }));
    expect(service.revokeShareLink).not.toHaveBeenCalled();
    await user.click(within(lista).getByRole("button", { name: /sí, revocar/i }));

    await waitFor(() =>
      expect(screen.queryByRole("list", { name: /enlaces vigentes/i })).not.toBeInTheDocument(),
    );
    expect(service.revokeShareLink).toHaveBeenCalledWith("t-1", "l-viejo");
  });

  it("cancelar la confirmación no revoca", async () => {
    const user = userEvent.setup();
    vi.mocked(service.listShareLinks).mockResolvedValue([EXISTENTE]);
    abrir();
    const lista = await screen.findByRole("list", { name: /enlaces vigentes/i });

    await user.click(within(lista).getByRole("button", { name: /^revocar/i }));
    await user.click(within(lista).getByRole("button", { name: /cancelar/i }));

    expect(service.revokeShareLink).not.toHaveBeenCalled();
    expect(within(lista).getByRole("button", { name: /^revocar/i })).toBeInTheDocument();
  });

  it("revocar el enlace recién generado también oculta su URL", async () => {
    const user = userEvent.setup();
    abrir();
    await user.click(await screen.findByRole("button", { name: /generar enlace/i }));
    const lista = await screen.findByRole("list", { name: /enlaces vigentes/i });

    await user.click(within(lista).getByRole("button", { name: /^revocar/i }));
    await user.click(within(lista).getByRole("button", { name: /sí, revocar/i }));

    await waitFor(() => expect(screen.queryByDisplayValue(CREADO.url)).not.toBeInTheDocument());
  });

  it("si no se puede generar muestra el error del backend", async () => {
    const user = userEvent.setup();
    vi.mocked(service.createShareLink).mockRejectedValue(
      new ApiError(403, "Tu rol en esta empresa no permite compartir licitaciones."),
    );
    abrir();

    await user.click(await screen.findByRole("button", { name: /generar enlace/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Tu rol en esta empresa no permite compartir licitaciones.",
    );
  });

  it("si revocar falla lo avisa y el enlace sigue en la lista", async () => {
    const user = userEvent.setup();
    vi.mocked(service.listShareLinks).mockResolvedValue([EXISTENTE]);
    vi.mocked(service.revokeShareLink).mockRejectedValue(new Error("red caída"));
    abrir();
    const lista = await screen.findByRole("list", { name: /enlaces vigentes/i });

    await user.click(within(lista).getByRole("button", { name: /^revocar/i }));
    await user.click(within(lista).getByRole("button", { name: /sí, revocar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/no se pudo revocar/i);
    expect(within(lista).getAllByRole("listitem")).toHaveLength(1);
  });

  it("se cierra con el botón y con Escape", async () => {
    const user = userEvent.setup();
    const onClose = abrir();

    await user.click(await screen.findByRole("button", { name: /cerrar/i }));
    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
