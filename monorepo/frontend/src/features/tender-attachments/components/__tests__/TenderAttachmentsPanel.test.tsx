import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import { formatDateTime } from "@/features/matches/utils/format";
import * as service from "../../services/tenderAttachmentsService";
import { buildOfficialAttachment, buildTenderAttachments } from "../../test-utils";
import { TenderAttachmentsPanel } from "../TenderAttachmentsPanel";

vi.mock("../../services/tenderAttachmentsService", () => ({
  getTenderAttachments: vi.fn(),
}));

const FICHA = "https://buscador.mercadopublico.cl/ficha?code=5052-431-COT26";

function renderPanel() {
  return render(<TenderAttachmentsPanel tenderId="t-1" tenderCode="5052-431-COT26" />);
}

function fichaLink() {
  return screen.getByRole("link", { name: /ver documentos en mercado público/i });
}

describe("TenderAttachmentsPanel", () => {
  beforeEach(() => {
    vi.mocked(service.getTenderAttachments).mockReset();
  });

  it("mientras carga avisa y deja a mano la ficha oficial", () => {
    vi.mocked(service.getTenderAttachments).mockReturnValue(new Promise(() => {}));

    renderPanel();

    expect(screen.getByRole("status")).toHaveTextContent("Cargando anexos de la licitación…");
    expect(fichaLink()).toHaveAttribute("href", FICHA);
    expect(fichaLink()).toHaveAttribute("target", "_blank");
  });

  it("lista cada anexo con su extensión y su estado", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [
          buildOfficialAttachment(),
          buildOfficialAttachment({
            id: "a-2",
            mp_document_id: 1931003,
            name: "anexos (1,1-A, 2).docx",
            ext: "docx",
          }),
        ],
      }),
    );

    renderPanel();

    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[0]).getByText("Anexo 3 Composición personalidad juridica.xlsx")).toBeVisible();
    expect(within(items[0]).getByText("XLSX")).toBeVisible();
    expect(within(items[0]).getByText("Falta")).toBeVisible();
    expect(within(items[1]).getByText("anexos (1,1-A, 2).docx")).toBeVisible();
    expect(within(items[1]).getByText("DOCX")).toBeVisible();
    expect(service.getTenderAttachments).toHaveBeenCalledWith("t-1");
    expect(
      screen.getByText(
        `Lista sincronizada con Mercado Público el ${formatDateTime("2026-09-28T16:28:00Z")}.`,
      ),
    ).toBeVisible();
  });

  it("no muestra la insignia de extensión cuando el nombre no la trae", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({
        official: [buildOfficialAttachment({ name: "Bases", ext: "" })],
      }),
    );

    renderPanel();

    const [item] = await screen.findAllByRole("listitem");
    expect(within(item).getByText("Bases")).toBeVisible();
    expect(within(item).getByText("Falta")).toBeVisible();
    expect(within(item).queryByText("XLSX")).not.toBeInTheDocument();
  });

  it("sin lista y sin sincronizar dice que todavía no la tiene", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ official: [], list_synced_at: null }),
    );

    renderPanel();

    expect(await screen.findByText(/Todavía no tenemos la lista de anexos/)).toBeVisible();
    expect(fichaLink()).toHaveAttribute("href", FICHA);
  });

  it("sin anexos y sincronizada dice que Mercado Público no informa ninguno", async () => {
    vi.mocked(service.getTenderAttachments).mockResolvedValue(
      buildTenderAttachments({ official: [] }),
    );

    renderPanel();

    expect(
      await screen.findByText("Mercado Público no informa anexos para esta licitación."),
    ).toBeVisible();
    expect(screen.queryByText(/Todavía no tenemos/)).not.toBeInTheDocument();
  });

  it("ante un error muestra el mensaje, conserva el enlace y permite reintentar", async () => {
    const user = userEvent.setup();
    vi.mocked(service.getTenderAttachments)
      .mockRejectedValueOnce(new ApiError(500, "Falló el servidor"))
      .mockResolvedValueOnce(buildTenderAttachments());

    renderPanel();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Falló el servidor");
    expect(fichaLink()).toBeVisible();

    await user.click(within(alert).getByRole("button", { name: "Reintentar" }));

    expect(await screen.findAllByRole("listitem")).toHaveLength(1);
    expect(service.getTenderAttachments).toHaveBeenCalledTimes(2);
  });
});
