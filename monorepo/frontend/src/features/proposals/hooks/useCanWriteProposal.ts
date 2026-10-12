"use client";

import { useWorkspace } from "@/features/workspaces/WorkspaceContext";

/**
 * ¿Puede el usuario generar postulaciones en la empresa activa?
 *
 * Sin espacio de trabajo cargado opera sobre su propia empresa, igual que el
 * backend (`_exigir_permiso`); la API sigue siendo la que decide.
 */
export function useCanWriteProposal(): boolean {
  const { activeWorkspace, hasPermission } = useWorkspace();
  return activeWorkspace === null || hasPermission("generate_proposal");
}
