import type { Metadata } from "next";
import Link from "next/link";
import "./../globals.css";

export const metadata: Metadata = {
  title: "ProyectosYa",
  description: "Plataforma de matching para licitaciones públicas",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-bg-page font-sans selection:bg-teal-200 selection:text-warm-900">
        <header className="border-b border-border-subtle bg-white shadow-xs">
          <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
            <Link href="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
              <div
                aria-hidden
                className="size-8 rounded-md bg-primary shadow-teal"
              />
              <span className="font-display text-xl font-bold tracking-tight text-text-strong">
                ProyectosYa
              </span>
            </Link>
            <Link
              href="/login"
              className="rounded-full bg-primary-soft px-4 py-2 text-sm font-semibold text-primary transition-all hover:bg-primary hover:text-white"
            >
              Iniciar sesión
            </Link>
          </div>
        </header>
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-12">
          {children}
        </main>
      </body>
    </html>
  );
}
