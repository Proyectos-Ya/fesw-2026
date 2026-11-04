import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { CompanyProvider } from "@/features/company-profile/components/CompanyProvider";
import { AccessibilityControls } from "@/features/shared/components/AccessibilityControls";
import { PreferencesProvider } from "@/features/shared/context/PreferencesContext";

export const metadata: Metadata = {
  title: "Chiripa - Configura tu perfil",
  description: "Construye tu perfil inteligente para empezar a recibir matches",
};

export default function OnboardingLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full bg-bg-page text-text-body font-sans selection:bg-primary-soft selection:text-text-strong">
        <PreferencesProvider>
          <AuthProvider>
            <RequireAuth>
              <CompanyProvider>
                <header className="border-b border-border-subtle bg-surface-card/80 backdrop-blur-md">
                  <div className="mx-auto flex min-h-16 max-w-3xl flex-wrap items-center justify-between gap-3 px-4 sm:px-6 py-2">
                    <Link href="/" className="inline-block">
                      <Image
                        src="/logo-color-light.svg"
                        alt="Chiripa"
                        width={130}
                        height={32}
                        priority
                        className="block dark:hidden"
                      />
                      <Image
                        src="/logo-color-dark.svg"
                        alt="Chiripa"
                        width={130}
                        height={32}
                        priority
                        className="hidden dark:block"
                      />
                    </Link>
                    <div className="flex items-center gap-3">
                      <span className="hidden sm:inline text-xs font-bold uppercase tracking-caps text-text-subtle">
                        Configura tu perfil
                      </span>
                      <AccessibilityControls compact />
                    </div>
                  </div>
                </header>
                <main className="mx-auto max-w-3xl px-4 sm:px-6 py-8 sm:py-10">
                  {children}
                </main>
              </CompanyProvider>
            </RequireAuth>
          </AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
