import type { Metadata } from "next";
import "../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";

export const metadata: Metadata = {
  title: "ProyectosYa - Autenticación",
  description: "Inicia sesión o crea tu cuenta en ProyectosYa",
};

export default function AuthLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="h-full bg-white font-sans selection:bg-teal-200 selection:text-warm-900">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
