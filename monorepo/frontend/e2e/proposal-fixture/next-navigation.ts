/** Doble de `next/navigation` para el fixture: el e2e no navega fuera de la página. */
export function useRouter() {
  return { push: () => {}, back: () => {}, replace: () => {}, refresh: () => {} };
}
