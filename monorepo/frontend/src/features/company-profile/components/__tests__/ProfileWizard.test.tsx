import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProfileWizard } from "../ProfileWizard";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import type { Supplier } from "../../services/supplierService";

// Los pasos 1 a 3 se reemplazan por botones que entregan datos válidos: lo que
// se prueba acá es qué hace el wizard al enviar y cómo reparte la revisión de lo
// importado, no los formularios. El botón "listo" respeta `nextBlocked`, como el
// "Siguiente" real; el botón "forzar" lo ignora para probar la guarda del envío.
const { STEP1, STEP2, STEP3, IMPORT_A, IMPORT_B } = vi.hoisted(() => {
  const base = {
    source: "sre",
    is_active: true,
    keywords: [],
    notices: [],
  };
  return {
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
    IMPORT_A: {
      ...base,
      rut: "76668304-5",
      legal_name: "Empresa A SpA",
      regions: ["Metropolitana", "Valparaíso"],
      sectors: ["Servicios de limpieza industrial"],
    },
    IMPORT_B: {
      ...base,
      rut: "76086428-5",
      legal_name: "Empresa B SpA",
      regions: ["Biobío"],
      sectors: ["Servicios de construcción y mantenimiento"],
    },
  };
});

interface MockReview {
  status?: string;
  onConfirm: () => void;
}

vi.mock("../steps/Step1Identity", () => ({
  Step1Identity: ({
    onNext,
    onImported,
    legalNameReview,
    nextBlocked,
  }: {
    onNext: (data: typeof STEP1) => void;
    onImported: (profile: typeof IMPORT_A) => void;
    legalNameReview: MockReview;
    nextBlocked: boolean;
  }) => (
    <div>
      <button onClick={() => onImported(IMPORT_A)}>importar RUT A</button>
      <button onClick={() => onImported(IMPORT_B)}>importar RUT B</button>
      <button onClick={legalNameReview.onConfirm}>confirmar razón social</button>
      <span>razón social: {legalNameReview.status ?? "sin revisión"}</span>
      <button disabled={nextBlocked} onClick={() => onNext(STEP1)}>
        paso 1 listo
      </button>
      <button onClick={() => onNext(STEP1)}>forzar avance del paso 1</button>
    </div>
  ),
}));
vi.mock("../steps/Step2Operations", () => ({
  Step2Operations: ({
    onNext,
    defaultValues,
    regionsReview,
    nextBlocked,
  }: {
    onNext: (data: typeof STEP2) => void;
    defaultValues: { regions?: string[] };
    regionsReview: MockReview;
    nextBlocked: boolean;
  }) => (
    <div>
      <span>regiones: {(defaultValues.regions ?? []).join(", ") || "ninguna"}</span>
      <button onClick={regionsReview.onConfirm}>confirmar regiones</button>
      <button disabled={nextBlocked} onClick={() => onNext(STEP2)}>
        paso 2 listo
      </button>
    </div>
  ),
}));
vi.mock("../steps/Step3Specialization", () => ({
  Step3Specialization: ({
    onNext,
    sectorsReview,
    nextBlocked,
    dismissedKeywords = [],
    onDismissKeyword,
  }: {
    onNext: (data: typeof STEP3) => void;
    sectorsReview: MockReview;
    nextBlocked: boolean;
    dismissedKeywords?: string[];
    onDismissKeyword?: (keyword: string) => void;
  }) => (
    <div>
      <button onClick={sectorsReview.onConfirm}>confirmar rubros</button>
      <button disabled={nextBlocked} onClick={() => onNext(STEP3)}>
        paso 3 listo
      </button>
      <button onClick={() => onNext(STEP3)}>forzar avance del paso 3</button>
      <button onClick={() => onDismissKeyword?.("pintura")}>descartar pintura</button>
      <p>descartadas: {dismissedKeywords.join(",")}</p>
    </div>
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

describe("ProfileWizard: la empresa encontrada tiene que ser la enviada", () => {
  // `waitForMySupplier` devuelve la empresa del usuario, sea cual sea. Un 409
  // puede significar "ya tienes OTRA empresa", y ahí dar por bueno el envío
  // descartaría en silencio el perfil que la persona acaba de escribir.
  beforeEach(() => {
    createSupplierMock.mockReset();
    waitForMySupplierMock.mockReset();
    setSupplierMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("un 409 por otra empresa distinta no se presenta como éxito", async () => {
    createSupplierMock.mockRejectedValue(
      new ApiError(409, "Ya tienes una empresa registrada"),
    );
    waitForMySupplierMock.mockResolvedValue({
      ...SUPPLIER,
      id: "sup-2",
      rut: "77.777.777-7",
    });
    renderAtSummary();

    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ya tienes una empresa registrada",
    );
    expect(screen.queryByText(SUCCESS_TITLE)).not.toBeInTheDocument();
    expect(setSupplierMock).not.toHaveBeenCalled();
  });

  it("acepta el éxito aunque el RUT vuelva en otro formato", async () => {
    createSupplierMock.mockRejectedValue(new TimeoutError());
    waitForMySupplierMock.mockResolvedValue({ ...SUPPLIER, rut: "76086428-5" });
    renderAtSummary();

    await submit();

    expect(await screen.findByText(SUCCESS_TITLE)).toBeInTheDocument();
    expect(setSupplierMock).toHaveBeenCalled();
  });
});

describe("ProfileWizard: datos importados", () => {
  beforeEach(() => {
    createSupplierMock.mockReset();
    waitForMySupplierMock.mockReset();
    setSupplierMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  const click = (name: string) => fireEvent.click(screen.getByText(name));

  it("no envía si un campo importado sigue sin confirmar", async () => {
    render(<ProfileWizard />);
    click("importar RUT A");
    click("confirmar razón social");
    click("paso 1 listo");
    click("confirmar regiones");
    click("paso 2 listo");
    // Los rubros quedan pendientes y el paso se salta el bloqueo.
    click("forzar avance del paso 3");

    await submit();

    expect(createSupplierMock).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent(/sin confirmar/i);
  });

  it("recorre el wizard: importa, confirma en cada paso, reimporta con otro RUT y guarda", async () => {
    createSupplierMock.mockResolvedValue(SUPPLIER);
    render(<ProfileWizard />);

    // Importación con el RUT A: la razón social queda pendiente y bloquea el paso 1.
    click("importar RUT A");
    expect(screen.getByText("razón social: pending")).toBeInTheDocument();
    expect(screen.getByText("paso 1 listo")).toBeDisabled();
    click("confirmar razón social");
    expect(screen.getByText("razón social: confirmed")).toBeInTheDocument();
    click("paso 1 listo");

    // Regiones: precargadas y pendientes.
    expect(screen.getByText("regiones: Metropolitana, Valparaíso")).toBeInTheDocument();
    expect(screen.getByText("paso 2 listo")).toBeDisabled();
    click("confirmar regiones");
    click("paso 2 listo");

    // Rubros.
    expect(screen.getByText("paso 3 listo")).toBeDisabled();
    click("confirmar rubros");
    click("paso 3 listo");

    // Desde el resumen se vuelve al paso 1 y se reimporta con otro RUT.
    fireEvent.click(screen.getAllByText("Editar")[0]);
    click("importar RUT B");
    expect(screen.getByText("razón social: pending")).toBeInTheDocument();
    click("confirmar razón social");
    click("paso 1 listo");

    // Las regiones del RUT A se vaciaron y solo quedan las del RUT B.
    expect(screen.getByText("regiones: Biobío")).toBeInTheDocument();
    expect(screen.getByText("paso 2 listo")).toBeDisabled();
    click("confirmar regiones");
    click("paso 2 listo");
    click("confirmar rubros");
    click("paso 3 listo");

    await submit();

    expect(createSupplierMock).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(SUCCESS_TITLE)).toBeInTheDocument();
  });
});

describe("ProfileWizard: sugerencias descartadas", () => {
  it("una sugerencia descartada sigue descartada al salir del paso 3 y volver", () => {
    render(<ProfileWizard />);
    fireEvent.click(screen.getByText("paso 1 listo"));
    fireEvent.click(screen.getByText("paso 2 listo"));
    fireEvent.click(screen.getByText("descartar pintura"));
    fireEvent.click(screen.getByText("paso 3 listo"));

    fireEvent.click(screen.getByRole("button", { name: /Volver/ }));

    expect(screen.getByText("descartadas: pintura")).toBeInTheDocument();
  });
});
