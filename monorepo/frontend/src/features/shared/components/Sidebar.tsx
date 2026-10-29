"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "./Icon";
import { Avatar } from "./Avatar";
import { AccessibilityControls } from "./AccessibilityControls";
import { useCompany } from "@/features/company-profile/components/CompanyProvider";
import { useAuth } from "@/features/auth/AuthContext";
import { useUnreadCount } from "@/features/notifications/hooks/useNotifications";

import { WorkspaceSelector } from "@/features/workspaces/components/WorkspaceSelector";
import { useWorkspace } from "@/features/workspaces/WorkspaceContext";

interface NavItemProps {
  icon: string;
  label: string;
  href: string;
  active?: boolean;
  badge?: number;
  onNavigate?: () => void;
}

function NavItem({ icon, label, href, active, badge, onNavigate }: NavItemProps) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-md transition-all duration-200 group ${
        active
          ? "bg-primary-soft text-primary font-bold shadow-sm"
          : "text-text-muted hover:bg-surface-hover hover:text-text-strong"
      }`}
    >
      <Icon
        name={icon}
        size={20}
        color={active ? "var(--primary)" : "var(--text-subtle)"}
        className="transition-colors group-hover:text-text-strong"
      />
      <span className="flex-1 text-sm">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span
          className={`px-2 py-0.5 rounded-full text-[0.625rem] font-bold ${
            active ? "bg-primary text-on-primary" : "bg-surface-inset text-text-muted"
          }`}
        >
          {badge}
        </span>
      )}
    </Link>
  );
}

const NAV_ITEMS: ReadonlyArray<{ icon: string; label: string; href: string }> = [
  { icon: "sparkles", label: "Inicio", href: "/" },
  { icon: "search", label: "Buscar", href: "/buscar" },
  { icon: "target", label: "Matches", href: "/matches" },
  { icon: "bookmark", label: "Guardados", href: "/guardados" },
  { icon: "kanban", label: "Tablero", href: "/tablero" },
  { icon: "bell", label: "Alertas", href: "/alertas" },
];

// Solo visible cuando el usuario ya tiene una empresa asignada
const COMPANY_NAV_ITEM = {
  icon: "building-2",
  label: "Mi empresa",
  href: "/empresa",
} as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function BrandLogo({ width = 140, height = 36 }: { width?: number; height?: number }) {
  return (
    <>
      <Image
        src="/logo-color-light.svg"
        alt="Chiripa"
        width={width}
        height={height}
        priority
        className="block dark:hidden"
      />
      <Image
        src="/logo-color-dark.svg"
        alt="Chiripa"
        width={width}
        height={height}
        priority
        className="hidden dark:block"
      />
    </>
  );
}

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const { user, logout } = useAuth();
  const { company, logoUrl } = useCompany();
  const { activeWorkspace, invitations } = useWorkspace();
  const unreadCount = useUnreadCount();
  const [mobileOpen, setMobileOpen] = useState(false);
  const activeLogoUrl =
    logoUrl ??
    (company.status === "with-company"
      ? company.supplier.logo_url ?? null
      : null);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const totalNotifications = unreadCount + (invitations?.length ?? 0);

  const currentUser = {
    name: user?.full_name ?? "Usuario",
    company:
      activeWorkspace?.active_supplier_name ||
      (company.status === "with-company"
        ? company.supplier.legal_name
        : "Sin empresa"),
  };

  const navItems =
    company.status === "with-company" || activeWorkspace !== null
      ? [...NAV_ITEMS, COMPANY_NAV_ITEM]
      : NAV_ITEMS;

  const handleLogout = async () => {
    setMobileOpen(false);
    await logout();
    router.replace("/login");
  };

  return (
    <>
      {/* Barra superior móvil (< 768px) */}
      <div className="flex md:hidden items-center justify-between px-4 py-3 border-b border-border-subtle bg-surface-card sticky top-0 z-30">
        <Link href="/" className="inline-block">
          <BrandLogo width={124} height={32} />
        </Link>
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Abrir menú de navegación"
          aria-expanded={mobileOpen}
          className="inline-flex items-center justify-center rounded-lg border border-border-subtle bg-surface-inset p-2 text-text-strong hover:bg-surface-hover transition-colors"
        >
          <Icon name="menu" size={20} />
        </button>
      </div>

      {/* Fondo oscuro del Drawer móvil */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar principal (Drawer deslizable en móvil, columna fija en escritorio) */}
      <aside
        data-open={mobileOpen}
        className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] flex-none bg-surface-card border-r border-border-subtle flex flex-col p-4 gap-1 h-screen shadow-xs transition-transform duration-200 ease-in-out md:sticky md:top-0 md:z-auto md:w-64 md:max-w-none md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-2 py-3 mb-1">
          <Link
            href="/"
            onClick={() => setMobileOpen(false)}
            className="inline-block"
          >
            <BrandLogo width={140} height={36} />
          </Link>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label="Cerrar menú de navegación"
            className="md:hidden rounded-lg p-1.5 text-text-subtle hover:bg-surface-hover hover:text-text-strong transition-colors"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="mb-3 px-1">
          <WorkspaceSelector />
        </div>

        <nav
          className="flex-1 flex flex-col gap-1 overflow-y-auto"
          aria-label="Navegación principal"
        >
          {navItems.map((item) => (
            <NavItem
              key={item.href}
              icon={item.icon}
              label={item.label}
              href={item.href}
              active={isActive(pathname, item.href)}
              // Alertas lleva contador de avisos no leídos + invitaciones pendientes
              badge={item.href === "/alertas" ? totalNotifications : undefined}
              onNavigate={() => setMobileOpen(false)}
            />
          ))}
        </nav>

        <div className="pt-3 pb-2 border-t border-border-subtle">
          <AccessibilityControls />
        </div>

        <div className="pt-3 border-t border-border-subtle flex items-center gap-3 group">
          <Avatar
            name={currentUser.name}
            src={activeLogoUrl ?? undefined}
            size="md"
          />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-text-strong truncate">
              {currentUser.name}
            </div>
            <div className="text-xs text-text-subtle truncate">
              {currentUser.company}
            </div>
          </div>
          <Link
            href="/configuracion"
            onClick={() => setMobileOpen(false)}
            className="p-1.5 rounded-md text-text-subtle hover:bg-surface-hover hover:text-text-strong transition-all duration-200"
            title="Ajustes y configuración"
          >
            <Icon name="settings" size={18} />
          </Link>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="p-1.5 rounded-md text-text-subtle hover:bg-danger-soft hover:text-danger transition-all duration-200"
            title="Cerrar sesión"
          >
            <Icon name="log-out" size={18} />
          </button>
        </div>
      </aside>
    </>
  );
}
