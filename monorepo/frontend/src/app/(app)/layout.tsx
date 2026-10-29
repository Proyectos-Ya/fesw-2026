import type { Metadata } from "next";
import "./../globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { RequireAuth } from "@/features/auth/components/RequireAuth";
import { Sidebar } from "@/features/shared/components/Sidebar";
import { PreferencesProvider } from "@/features/shared/context/PreferencesContext";
import { CompanyProvider } from "@/features/company-profile/components/CompanyProvider";
import { WorkspaceProvider } from "@/features/workspaces/WorkspaceContext";

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
      <body className="min-h-full flex flex-col md:flex-row bg-bg-page text-text-body font-sans selection:bg-primary-soft selection:text-text-strong">
        <PreferencesProvider>
          <AuthProvider>
            <RequireAuth>
              <WorkspaceProvider>
                <CompanyProvider>
                  <Sidebar />
                  <div className="flex-1 flex flex-col min-w-0">
                    <main className="flex-1 min-w-0 p-4 sm:p-6 md:p-8 overflow-x-hidden overflow-y-auto">
                      {children}
                    </main>
                  </div>
                </CompanyProvider>
              </WorkspaceProvider>
            </RequireAuth>
          </AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
