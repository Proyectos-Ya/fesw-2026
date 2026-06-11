import type { Metadata } from "next";
import Link from "next/link";
import "../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { CompanyProvider } from "@/features/company-profile/components/CompanyProvider";

export const metadata: Metadata = {
  title: "ProyectosYa - Configura tu perfil",
  description: "Construye tu perfil inteligente para empezar a recibir matches",
};

export default function OnboardingLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full bg-bg-page font-sans selection:bg-teal-200 selection:text-warm-900">
        <AuthProvider>
          <RequireAuth>
          <CompanyProvider>
          <header className="border-b border-border-subtle bg-white/80 backdrop-blur-md">
            <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-6">
              <Link href="/" className="font-display text-xl font-bold tracking-tight text-text-strong">
                ProyectosYa
              </Link>
              <span className="text-xs font-bold uppercase tracking-caps text-text-subtle">
                Configura tu perfil
              </span>
            </div>
          </header>
          <main className="mx-auto max-w-3xl px-6 py-10">{children}</main>
          </CompanyProvider>
          </RequireAuth>
        </AuthProvider>
      </body>
    </html>
  );
}
