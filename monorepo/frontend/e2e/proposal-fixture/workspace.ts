/** Doble del espacio de trabajo: sin empresa activa, con permiso para postular. */
export function useWorkspace() {
  return { activeWorkspace: null, hasPermission: () => true };
}
