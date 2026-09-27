import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { InviteMemberModal } from "../components/InviteMemberModal";
import * as workspaceService from "../services/workspaceService";

vi.mock("../services/workspaceService", () => ({
  createInvitation: vi.fn(),
}));

describe("InviteMemberModal", () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    supplierId: "sup-123",
    supplierName: "Constructora Andes SpA",
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no renderiza nada si isOpen es false", () => {
    const { container } = render(
      <InviteMemberModal {...defaultProps} isOpen={false} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renderiza el modal correctamente con el nombre de la empresa", () => {
    render(<InviteMemberModal {...defaultProps} />);

    expect(
      screen.getByRole("heading", { name: "Invitar miembro" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Constructora Andes SpA")).toBeInTheDocument();
    expect(screen.getByLabelText("Correo electrónico del usuario")).toBeInTheDocument();
    expect(screen.getByLabelText("Rol asignado")).toBeInTheDocument();
  });

  it("muestra error si se intenta enviar un correo inválido", async () => {
    render(<InviteMemberModal {...defaultProps} />);

    const emailInput = screen.getByLabelText("Correo electrónico del usuario");
    fireEvent.change(emailInput, { target: { value: "invalid-email" } });

    const submitBtn = screen.getByRole("button", { name: "Invitar miembro" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Por favor ingresa un correo electrónico válido."),
      ).toBeInTheDocument();
    });
    expect(workspaceService.createInvitation).not.toHaveBeenCalled();
  });

  it("envía la invitación in-app y muestra mensaje de éxito al completar", async () => {
    vi.mocked(workspaceService.createInvitation).mockResolvedValueOnce({
      id: "inv-1",
      supplier_id: "sup-123",
      invited_by: "u-1",
      email: "socio@andes.cl",
      role: "admin",
      token: "tok-abc",
      status: "pending",
      expires_at: "2026-10-01",
      created_at: "2026-09-12",
    });

    render(<InviteMemberModal {...defaultProps} />);

    const emailInput = screen.getByLabelText("Correo electrónico del usuario");
    const roleSelect = screen.getByLabelText("Rol asignado");

    fireEvent.change(emailInput, { target: { value: "socio@andes.cl" } });
    fireEvent.change(roleSelect, { target: { value: "admin" } });

    const submitBtn = screen.getByRole("button", { name: "Invitar miembro" });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(workspaceService.createInvitation).toHaveBeenCalledWith({
        supplier_id: "sup-123",
        email: "socio@andes.cl",
        role: "admin",
      });
    });

    await waitFor(() => {
      expect(
        screen.getByText(/Invitación enviada con éxito a socio@andes.cl/),
      ).toBeInTheDocument();
    });
    expect(defaultProps.onSuccess).toHaveBeenCalled();
  });
});
