import type { Metadata } from "next";
import "../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { RedirectIfAuthenticated } from "@/features/auth/components/RedirectIfAuthenticated";
import { PreferencesProvider } from "@/features/shared/context/PreferencesContext";

export const metadata: Metadata = {
  title: "Chiripa - Autenticación",
  description: "Inicia sesión o crea tu cuenta en Chiripa",
};

export default function AuthLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="h-full bg-bg-page text-text-body font-sans selection:bg-primary-soft selection:text-text-strong">
        <PreferencesProvider>
          <AuthProvider>
            <RedirectIfAuthenticated>{children}</RedirectIfAuthenticated>
          </AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
