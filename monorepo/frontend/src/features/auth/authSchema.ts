import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Correo electrónico inválido"),
  password: z.string().min(8, "La contraseña debe tener al menos 8 caracteres"),
});

export type LoginData = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  email: z.string().email("Correo electrónico inválido"),
  password: z.string().min(8, "La contraseña debe tener al menos 8 caracteres"),
  full_name: z.string().min(2, "El nombre completo es requerido"),
  phone: z.string().optional(),
});

export type RegisterData = z.infer<typeof registerSchema>;

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  active: boolean;
  email_verified: boolean;
  created_at: string;
}
