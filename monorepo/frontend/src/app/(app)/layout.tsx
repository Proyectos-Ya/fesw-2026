import type { Metadata } from "next";
import "./../globals.css";
import { Sidebar } from "@/features/shared/components/Sidebar";
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
        <Sidebar />
        
        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-16 border-b border-border-subtle bg-white/80 backdrop-blur-md sticky top-0 z-10 flex items-center justify-between px-8">
            <div className="flex-1 max-w-md bg-warm-50 border border-border-default rounded-md px-3 py-2 flex items-center gap-2 group focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/10 transition-all">
              <Icon name="search" size={18} className="text-text-subtle group-focus-within:text-primary" />
              <input 
                placeholder="Buscar licitaciones..." 
                className="bg-transparent border-none outline-none text-sm w-full text-text-strong placeholder:text-text-subtle"
              />
            </div>
            
            <div className="flex items-center gap-4">
              <button className="p-2 rounded-full text-text-muted hover:bg-warm-100 hover:text-text-strong transition-colors relative">
                <Icon name="bell" size={20} />
                <span className="absolute top-2 right-2 size-2 bg-accent rounded-full border-2 border-white" />
              </button>
              <div className="h-8 w-px bg-border-subtle mx-2" />
              <div className="size-8 rounded-full bg-primary-soft flex items-center justify-center font-bold text-xs text-primary">
                JD
              </div>
            </div>
          </header>
          
          <main className="flex-1 p-8 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
