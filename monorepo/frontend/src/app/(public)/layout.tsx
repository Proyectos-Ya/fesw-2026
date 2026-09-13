import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "../globals.css";

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
      <body className="min-h-full bg-bg-page font-sans selection:bg-teal-200 selection:text-warm-900">
        <header className="border-b border-border-subtle bg-white/80 backdrop-blur-md">
          <div className="mx-auto flex h-16 max-w-3xl items-center px-6">
            <Link href="/" className="inline-block">
              <Image
                src="/logo-color-light.svg"
                alt="Chiripa"
                width={130}
                height={32}
                priority
              />
            </Link>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-6 py-12">{children}</main>
      </body>
    </html>
  );
}
