export type CertificationStatusKind = "expired" | "expiring_soon" | "valid" | "no_date";

export interface CertificationStatus {
  status: CertificationStatusKind;
  /** Días hasta el vencimiento. Negativo si ya venció. Ausente si no hay fecha válida. */
  daysLeft?: number;
  label: string;
}

/** Días de anticipación con los que una certificación pasa a "por vencer". */
const EXPIRING_SOON_DAYS = 30;

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * Calcula el estado de vigencia de una certificación.
 * Compara días de calendario (AAAA-MM-DD contra el día local de referenceDate),
 * así la hora del día y la zona horaria no mueven el resultado.
 */
export function getCertificationStatus(
  expiresAt: string | null | undefined,
  referenceDate: Date = new Date(),
): CertificationStatus {
  const noDate: CertificationStatus = { status: "no_date", label: "Sin vencimiento" };
  if (!expiresAt) return noDate;

  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(expiresAt);
  if (!match) return noDate;

  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const expiry = new Date(Date.UTC(year, month - 1, day));
  // Date.UTC normaliza fechas imposibles (31 de febrero), así que se descartan.
  if (expiry.getUTCMonth() !== month - 1 || expiry.getUTCDate() !== day) return noDate;

  const today = Date.UTC(
    referenceDate.getFullYear(),
    referenceDate.getMonth(),
    referenceDate.getDate(),
  );
  const daysLeft = Math.round((expiry.getTime() - today) / MS_PER_DAY);

  if (daysLeft < 0) return { status: "expired", daysLeft, label: "Vencida" };
  if (daysLeft === 0) return { status: "expiring_soon", daysLeft, label: "Vence hoy" };
  if (daysLeft <= EXPIRING_SOON_DAYS) {
    return {
      status: "expiring_soon",
      daysLeft,
      label: daysLeft === 1 ? "Vence en 1 día" : `Vence en ${daysLeft} días`,
    };
  }
  return { status: "valid", daysLeft, label: "Vigente" };
}

/**
 * Clave para comparar nombres de certificaciones: sin tildes, mayúsculas, espacios,
 * guiones, puntos ni guiones bajos. "ISO-9001" e "iso 9001" son la misma; los dígitos
 * y los dos puntos se conservan, así que "ISO 9001:2015" sigue siendo otra.
 * Es la misma regla que `_clave_certificacion` en el backend
 * (monorepo/backend/app/domain/entities/supplier.py).
 */
export function certificationKey(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[\s\-._]/g, "");
}

/** Recorta el nombre y deja un solo espacio entre palabras. */
export function cleanCertificationName(name: string): string {
  return name.trim().replace(/\s+/g, " ");
}
