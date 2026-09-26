/**
 * Licitación desde la que se salió a autorizar el calendario.
 *
 * Si el usuario cancela en Google, la respuesta no trae nada propio de la app
 * más que el `state`, que es opaco; esto permite ofrecerle volver a donde estaba.
 */
const KEY = "proyectosya.calendar-return-tender";

export function rememberCalendarReturnTender(tenderId: string): void {
  try {
    window.sessionStorage.setItem(KEY, tenderId);
  } catch {
    // Sin almacenamiento (modo privado, bloqueado): el retorno cae a /matches.
  }
}

export function consumeCalendarReturnTender(): string | null {
  try {
    const tenderId = window.sessionStorage.getItem(KEY);
    window.sessionStorage.removeItem(KEY);
    return tenderId;
  } catch {
    return null;
  }
}
