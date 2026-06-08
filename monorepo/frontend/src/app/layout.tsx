import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

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
    <html
      lang="es"
      className={`${inter.variable} ${outfit.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-zinc-50">
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6">
            <div className="flex items-center gap-3">
              <div
                aria-hidden
                className="size-8 rounded-button bg-brand-primary-500"
              />
              <span className="font-display text-lg font-semibold text-brand-primary-900">
                ProyectosYa
              </span>
            </div>
            <button
              type="button"
              className="rounded-button bg-brand-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-primary-700"
            >
              Iniciar sesión
            </button>
          </div>
        </header>
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-12">
          {children}
        </main>
      </body>
    </html>
  );
}
