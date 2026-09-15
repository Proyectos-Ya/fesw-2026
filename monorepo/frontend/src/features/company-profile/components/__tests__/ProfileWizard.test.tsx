import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileWizard } from "../ProfileWizard";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import type { Supplier } from "../../services/supplierService";

// Los pasos 1 a 3 se reemplazan por un botón que entrega datos válidos: lo que
// se prueba acá es qué hace el wizard al enviar, no los formularios.
const { STEP1, STEP2, STEP3 } = vi.hoisted(() => ({
  STEP1: { legal_name: "Constructora Demo SpA", rut: "76.086.428-5" },
  STEP2: {
    regions: ["Metropolitana de Santiago"],
    years_experience: 5,
    num_employees: 20,
  },
  STEP3: {
    sectors: ["Construcción"],
    keywords: [],
    certifications: [],
    description: "Empresa con amplia experiencia en obras civiles y edificación.",
  },
}));

vi.mock("../steps/Step1Identity", () => ({
  Step1Identity: ({ onNext }: { onNext: (data: typeof STEP1) => void }) => (
    <button onClick={() => onNext(STEP1)}>paso 1 listo</button>
  ),
}));
vi.mock("../steps/Step2Operations", () => ({
  Step2Operations: ({ onNext }: { onNext: (data: typeof STEP2) => void }) => (
    <button onClick={() => onNext(STEP2)}>paso 2 listo</button>
  ),
}));
vi.mock("../steps/Step3Specialization", () => ({
  Step3Specialization: ({ onNext }: { onNext: (data: typeof STEP3) => void }) => (
    <button onClick={() => onNext(STEP3)}>paso 3 listo</button>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({ user: { full_name: "Ana Pérez" } }),
}));

const setSupplierMock = vi.fn();
vi.mock("../CompanyProvider", () => ({
  useCompany: () => ({ setSupplier: setSupplierMock }),
}));

const createSupplierMock = vi.fn();
const waitForMySupplierMock = vi.fn();
vi.mock("../../services/supplierService", () => ({
  createSupplier: (...args: unknown[]) => createSupplierMock(...args),
  waitForMySupplier: (...args: unknown[]) => waitForMySupplierMock(...args),
}));

const SUPPLIER: Supplier = {
  id: "sup-1",
  user_id: "user-1",
  ...STEP1,
  ...STEP2,
  ...STEP3,
  trade_name: null,
  created_at: "2026-09-15T00:00:00Z",
  updated_at: "2026-09-15T00:00:00Z",
};

const SUCCESS_TITLE = "¡Perfil creado con éxito!";

function renderAtSummary() {
  render(<ProfileWizard />);
  fireEvent.click(screen.getByText("paso 1 listo"));
  fireEvent.click(screen.getByText("paso 2 listo"));
  fireEvent.click(screen.getByText("paso 3 listo"));
}

async function submit() {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /Guardar perfil y comenzar/ }));
  });
}

describe("ProfileWizard: envío", () => {
  beforeEach(() => {
    createSupplierMock.mockReset();
    waitForMySupplierMock.mockReset();
    setSupplierMock.mockReset();
  });

  it("muestra el éxito cuando el backend crea la empresa", async () => {
    createSupplierMock.mockResolvedValue(SUPPLIER);
    renderAtSummary();

    await submit();

    expect(await screen.findByText(SUCCESS_TITLE)).toBeInTheDocument();
    expect(setSupplierMock).toHaveBeenCalledWith(SUPPLIER);
    expect(waitForMySupplierMock).not.toHaveBeenCalled();
  });

  it("tras un timeout confirma con reintentos y termina en éxito si la empresa apareció", async () => {
    // Es el incidente del 3-sep: el cliente cortó a los 60 s y la empresa se
    // confirmó en el backend dos segundos después.
    createSupplierMock.mockRejectedValue(new TimeoutError());
    waitForMySupplierMock.mockResolvedValue(SUPPLIER);
    renderAtSummary();

    await submit();

    expect(await screen.findByText(SUCCESS_TITLE)).toBeInTheDocument();
    expect(setSupplierMock).toHaveBeenCalledWith(SUPPLIER);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("un 409 cuando la empresa ya es del usuario termina en éxito", async () => {
    createSupplierMock.mockRejectedValue(
      new ApiError(409, "Ya existe un proveedor con RUT 76.086.428-5"),
    );
    waitForMySupplierMock.mockResolvedValue(SUPPLIER);
    renderAtSummary();

    await submit();

    expect(await screen.findByText(SUCCESS_TITLE)).toBeInTheDocument();
  });

  it("un 503 sin empresa vuelve al resumen con el detalle del backend", async () => {
    createSupplierMock.mockRejectedValue(
      new ApiError(503, "No pudimos procesar el perfil de tu empresa a tiempo."),
    );
    waitForMySupplierMock.mockResolvedValue(null);
    renderAtSummary();

    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No pudimos procesar el perfil de tu empresa a tiempo.",
    );
    expect(
      screen.getByRole("button", { name: /Guardar perfil y comenzar/ }),
    ).toBeInTheDocument();
  });

  it("un timeout sin empresa muestra el mensaje de tiempo agotado", async () => {
    createSupplierMock.mockRejectedValue(new TimeoutError());
    waitForMySupplierMock.mockResolvedValue(null);
    renderAtSummary();

    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      new TimeoutError().message,
    );
  });

  it("un 400 no espera a la empresa: muestra el error de inmediato", async () => {
    createSupplierMock.mockRejectedValue(new ApiError(400, "RUT format is invalid"));
    renderAtSummary();

    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent("RUT format is invalid");
    expect(waitForMySupplierMock).not.toHaveBeenCalled();
  });
});

describe("ProfileWizard: pantalla de creación", () => {
  // El loader era un spinner de 16 px dentro del botón; lo único visible era la
  // barra de éxito, que aparece cuando todo ya terminó. La espera tiene que
  // verse desde el clic, porque puede durar casi un minuto.
  const pending = () => new Promise<never>(() => {});

  const beforeUnloadIsBlocked = () => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  };

  beforeEach(() => {
    createSupplierMock.mockReset();
    waitForMySupplierMock.mockReset();
    setSupplierMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("aparece apenas se aprieta el botón, sin esperar al backend", async () => {
    createSupplierMock.mockReturnValue(pending());
    renderAtSummary();

    await submit();

    expect(screen.getByRole("status")).toHaveTextContent("Creando tu empresa…");
    expect(
      screen.queryByRole("button", { name: /Guardar perfil y comenzar/ }),
    ).not.toBeInTheDocument();
  });

  it("pasa a la fase de verificación mientras confirma tras un timeout", async () => {
    createSupplierMock.mockRejectedValue(new TimeoutError());
    waitForMySupplierMock.mockReturnValue(pending());
    renderAtSummary();

    await submit();

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Confirmando que tu empresa quedó registrada…",
    );
  });

  it("advierte antes de cerrar o recargar la página mientras se crea", async () => {
    // Recargar a mitad de la petición fue lo que llevó al reintento del 3-sep.
    createSupplierMock.mockReturnValue(pending());
    renderAtSummary();

    await submit();

    expect(beforeUnloadIsBlocked()).toBe(true);
  });

  it("deja de advertir al volver al resumen tras un error", async () => {
    createSupplierMock.mockRejectedValue(new ApiError(400, "RUT format is invalid"));
    renderAtSummary();

    await submit();
    await screen.findByRole("alert");

    expect(beforeUnloadIsBlocked()).toBe(false);
  });
});
