import type { CompraAgilFillResult } from "../../adapters/mp/compra-agil-adapter";
import { PostulationPackagePayload } from "../../types/schemas";

export interface CompraAgilPanelState {
  packageData: PostulationPackagePayload;
  filledCount: number;
  incompleteCount: number;
  pending: string[];
  notice?: string;
}

export interface CompraAgilFlowDeps {
  tenderCode: string;
  getPackage: (tenderCode: string) => Promise<PostulationPackagePayload | null>;
  waitForForm: () => Promise<boolean>;
  getSessionRut: () => Promise<string | null>;
  fill: (pkg: PostulationPackagePayload, options: { sessionRut: string | null }) => Promise<CompraAgilFillResult>;
  render: (state: CompraAgilPanelState) => void;
}

const NOTICES: Record<NonNullable<CompraAgilFillResult["error"]>, string> = {
  FORM_NOT_FOUND: "No encontramos el formulario de cotización en esta página.",
  TENDER_CODE_MISMATCH: "Esta página corresponde a otra cotización. No completamos nada.",
  IDENTITY_UNVERIFIED: "No pudimos verificar la empresa con la que iniciaste sesión. No completamos nada.",
  RUT_MISMATCH: "Iniciaste sesión con otra empresa distinta a la del borrador. No completamos nada.",
};

/** Aplica el paquete pendiente al formulario de Compra Ágil (CA4, CA6, CA7). Nunca envía (CA8). */
export async function runCompraAgilFlow(deps: CompraAgilFlowDeps): Promise<void> {
  const pkg = await deps.getPackage(deps.tenderCode);
  if (!pkg) return;

  const empty = { packageData: pkg, filledCount: 0, incompleteCount: 0, pending: [] };

  if (!(await deps.waitForForm())) {
    deps.render({ ...empty, notice: NOTICES.FORM_NOT_FOUND });
    return;
  }

  const result = await deps.fill(pkg, { sessionRut: await deps.getSessionRut() });
  if (!result.success) {
    deps.render({ ...empty, notice: result.error ? NOTICES[result.error] : NOTICES.FORM_NOT_FOUND });
    return;
  }

  deps.render({
    packageData: pkg,
    filledCount: result.filledCount,
    incompleteCount: result.incompleteCount,
    pending: result.pending,
  });
}
