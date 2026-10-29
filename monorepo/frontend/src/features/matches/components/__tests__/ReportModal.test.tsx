import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ReportModal } from "../ReportModal";
import * as tenderService from "../../services/tenderService";

describe("ReportModal", () => {
  it("muestra el formulario breve para explicar descontento y razones (S1/S2)", () => {
    render(
      <ReportModal
        open={true}
        kind="match"
        tenderId="tender-123"
        tenderTitle="Suministro de computadores"
        onClose={vi.fn()}
      />
    );

    expect(screen.getByRole("heading", { name: /Reportar mal match/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Razón o motivo del reporte/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Enviar reporte/i })).toBeInTheDocument();
  });

  it("envía el reporte y llama onClose y onSuccess al completar", async () => {
    const reportSpy = vi.spyOn(tenderService, "reportMatch").mockResolvedValueOnce({
      id: "rep-1",
      tender_id: "tender-123",
      kind: "match",
      reason: "No vendemos computadores, vendemos muebles",
    });
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    render(
      <ReportModal
        open={true}
        kind="match"
        tenderId="tender-123"
        onClose={onClose}
        onSuccess={onSuccess}
      />
    );

    const textarea = screen.getByLabelText(/Razón o motivo del reporte/i);
    fireEvent.change(textarea, { target: { value: "No vendemos computadores, vendemos muebles" } });

    const submitBtn = screen.getByRole("button", { name: /Enviar reporte/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(reportSpy).toHaveBeenCalledWith("tender-123", {
        kind: "match",
        reason: "No vendemos computadores, vendemos muebles",
      });
      expect(onSuccess).toHaveBeenCalled();
      expect(onClose).toHaveBeenCalled();
    });
  });
});
