import type { Metadata } from "next";
import "./../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { Sidebar } from "@/features/shared/components/Sidebar";
import { AppHeader } from "@/features/shared/components/AppHeader";
import { Icon } from "@/features/shared/components/Icon";

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
      <body className="min-h-full flex bg-bg-page font-sans selection:bg-teal-200 selection:text-warm-900">
        <AuthProvider>
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <AppHeader />
            <main className="flex-1 p-8 overflow-auto">{children}</main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
