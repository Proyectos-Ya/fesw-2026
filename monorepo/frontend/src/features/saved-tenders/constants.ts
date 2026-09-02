export const SAVED_TENDERS_ERRORS = {
  SAVE_FAILED:
    "No se pudo guardar la licitación. La operación no pudo realizarse y se mantuvo el estado anterior.",
  UNSAVE_FAILED:
    "No se pudo quitar la licitación. La operación no pudo realizarse y se mantuvo el estado anterior.",
} as const;

export function getSaveErrorMessage(isCurrentlySaved: boolean): string {
  return isCurrentlySaved
    ? SAVED_TENDERS_ERRORS.UNSAVE_FAILED
    : SAVED_TENDERS_ERRORS.SAVE_FAILED;
}
