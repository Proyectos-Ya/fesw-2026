import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/features/shared/api/client";
import * as calendarService from "../../services/calendarService";
import { rememberCalendarReturnTender } from "../../utils/calendarReturn";
import { CalendarOAuthCallback } from "../CalendarOAuthCallback";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
}));

vi.mock("../../services/calendarService", () => ({
  completeCalendarAuthorization: vi.fn(),
}));

const RESULTADO = {
  provider: "google" as const,
  tender_id: "t-1",
  milestone_ids: ["m-1"],
  default_time: "09:00",
  account_email: "usuario@gmail.com",
};

describe("CalendarOAuthCallback", () => {
  beforeEach(() => {
    replace.mockReset();
    vi.mocked(calendarService.completeCalendarAuthorization).mockReset();
    window.sessionStorage.clear();
  });

  it("completa la conexión y vuelve a la licitación", async () => {
    vi.mocked(calendarService.completeCalendarAuthorization).mockResolvedValue(RESULTADO);

    render(<CalendarOAuthCallback provider="google" code="codigo" state="estado" error={null} />);

    expect(screen.getByRole("status")).toHaveTextContent(/conectando con google calendar/i);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/matches/t-1?calendario=google"));
    expect(calendarService.completeCalendarAuthorization).toHaveBeenCalledWith("google", "codigo", "estado");
  });

  it("no usa el código dos veces aunque React monte dos veces el efecto", async () => {
    vi.mocked(calendarService.completeCalendarAuthorization).mockResolvedValue(RESULTADO);

    render(
      <StrictMode>
        <CalendarOAuthCallback provider="google" code="codigo" state="estado" error={null} />
      </StrictMode>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalled());
    expect(calendarService.completeCalendarAuthorization).toHaveBeenCalledTimes(1);
  });

  it("si el usuario canceló en Google lo explica y ofrece volver a la licitación", async () => {
    rememberCalendarReturnTender("t-9");

    render(<CalendarOAuthCallback provider="google" code={null} state="estado" error="access_denied" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/cancelaste la conexión con google calendar/i);
    expect(screen.getByRole("link", { name: /volver a la licitación/i })).toHaveAttribute("href", "/matches/t-9");
    expect(calendarService.completeCalendarAuthorization).not.toHaveBeenCalled();
  });

  it("muestra el error del backend y permite volver", async () => {
    rememberCalendarReturnTender("t-9");
    vi.mocked(calendarService.completeCalendarAuthorization).mockRejectedValue(
      new ApiError(400, "La autorización no es válida o expiró."),
    );

    render(<CalendarOAuthCallback provider="google" code="codigo" state="estado" error={null} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("La autorización no es válida o expiró.");
    expect(screen.getByRole("link", { name: /volver a la licitación/i })).toHaveAttribute("href", "/matches/t-9");
  });

  it("sin licitación recordada vuelve a las recomendaciones", async () => {
    render(<CalendarOAuthCallback provider="google" code={null} state={null} error={null} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/no recibimos la autorización/i);
    expect(screen.getByRole("link", { name: /volver/i })).toHaveAttribute("href", "/matches");
  });
});
