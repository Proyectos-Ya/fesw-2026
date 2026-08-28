import { z } from "zod";

const rutRegex = /^(\d{1,3}(\.\d{3})*|\d{7,8})-[\dkK]$/;

/** Valida el dígito verificador de un RUT chileno (módulo 11). */
export function isValidRut(rut: string): boolean {
  const cleaned = rut.replace(/\./g, "").replace(/-/g, "").toUpperCase();
  if (cleaned.length < 2) return false;

  const body = cleaned.slice(0, -1);
  const checkDigit = cleaned.slice(-1);
  if (!/^\d+$/.test(body)) return false;

  const multipliers = [2, 3, 4, 5, 6, 7];
  const total = [...body]
    .reverse()
    .reduce((sum, digit, i) => sum + Number(digit) * multipliers[i % 6], 0);
  const remainder = 11 - (total % 11);
  const expected = remainder === 11 ? "0" : remainder === 10 ? "K" : String(remainder);

  return checkDigit === expected;
}

export const step1Schema = z.object({
  legal_name: z
    .string()
    .min(2, "El nombre debe tener al menos 2 caracteres.")
    .max(150, "El nombre no puede superar los 150 caracteres."),
  trade_name: z
    .string()
    .max(150, "El nombre no puede superar los 150 caracteres.")
    .optional(),
  rut: z
    .string()
    .regex(rutRegex, "RUT inválido. Formato: 12.345.678-9")
    .refine(isValidRut, "El RUT no es válido. Revisa el dígito verificador."),
});

export const step2Schema = z.object({
  regions: z.array(z.string()).min(1, "Selecciona al menos una región."),
  years_experience: z
    .number({ error: "Ingresa un número válido." })
    .int("Debe ser un número entero.")
    .min(0, "El valor mínimo es 0.")
    .max(100, "El valor máximo es 100."),
  num_employees: z
    .number({ error: "Ingresa un número válido." })
    .int("Debe ser un número entero.")
    .min(1, "La empresa debe tener al menos 1 empleado.")
    .max(100000, "El valor ingresado no es válido."),
});

export const step3Schema = z.object({
  sectors: z.array(z.string()).min(1, "Selecciona al menos un rubro."),
  keywords: z.array(z.string()),
  certifications: z.array(z.string()),
  description: z
    .string()
    .min(30, "La descripción debe tener al menos 30 caracteres.")
    .max(1000, "La descripción no puede superar los 1000 caracteres."),
});

export const profileSchema = step1Schema.extend(step2Schema.shape).extend(step3Schema.shape);

export type Step1Data = z.infer<typeof step1Schema>;
export type Step2Data = z.infer<typeof step2Schema>;
export type Step3Data = z.infer<typeof step3Schema>;
export type ProfileData = z.infer<typeof profileSchema>;
