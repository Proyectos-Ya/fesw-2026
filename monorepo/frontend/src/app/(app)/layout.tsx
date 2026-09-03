import type { Metadata } from "next";
import "./../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { Sidebar } from "@/features/shared/components/Sidebar";
import { CompanyProvider } from "@/features/company-profile/components/CompanyProvider";

export const metadata: Metadata = {
  title: "Chiripa",
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
          <RequireAuth>
            <CompanyProvider>
              <Sidebar />
              <div className="flex-1 flex flex-col min-w-0">
                <main className="flex-1 p-8 overflow-auto">{children}</main>
              </div>
            </CompanyProvider>
          </RequireAuth>
        </AuthProvider>
      </body>
    </html>
  );
}
