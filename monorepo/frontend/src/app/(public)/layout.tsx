import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "../globals.css";
import { AccessibilityControls } from "@/features/shared/components/AccessibilityControls";
import { PreferencesProvider } from "@/features/shared/context/PreferencesContext";

export const metadata: Metadata = {
  title: "Chiripa",
};

/**
 * Layout de las páginas públicas: sin sesión, sin proveedores de contexto.
 *
 * Existe como grupo aparte porque este proyecto no tiene un layout raíz en
 * `src/app/`: cada grupo declara su propio `<html>`. Meter estas páginas en
 * `(app)` las pondría detrás de `RequireAuth`, y en `(auth)` detrás de
 * `RedirectIfAuthenticated`, que echaría a quien ya inició sesión. Una política
 * de privacidad tiene que poder leerla cualquiera, con sesión o sin ella —
 * incluido el revisor de Google, que comprueba que la URL responda.
 */
export default function PublicLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full bg-bg-page text-text-body font-sans selection:bg-primary-soft selection:text-text-strong">
        <PreferencesProvider>
          <header className="border-b border-border-subtle bg-surface-card/80 backdrop-blur-md">
            <div className="mx-auto flex min-h-16 max-w-3xl items-center justify-between gap-3 px-4 sm:px-6 py-2">
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
              <AccessibilityControls compact />
            </div>
          </header>
          <main className="mx-auto max-w-3xl px-4 sm:px-6 py-8 sm:py-12">
            {children}
          </main>
        </PreferencesProvider>
      </body>
    </html>
  );
}
