"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "./Icon";
import { Avatar } from "./Avatar";
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
}

function NavItem({ icon, label, href, active, badge }: NavItemProps) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-md transition-all duration-200 group ${
        active
          ? "bg-primary-soft text-primary font-bold shadow-sm"
          : "text-text-muted hover:bg-warm-100 hover:text-text-strong"
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
          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
            active ? "bg-primary text-white" : "bg-warm-200 text-text-muted"
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

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const { user, logout } = useAuth();
  const { company } = useCompany();
  const { activeWorkspace, invitations } = useWorkspace();
  const unreadCount = useUnreadCount();

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
    await logout();
    router.replace("/login");
  };

  return (
    <aside className="w-64 flex-none bg-white border-r border-border-subtle flex flex-col p-4 gap-1 sticky top-0 h-screen shadow-xs">
      <div className="px-2 py-3 mb-1">
        <Link href="/" className="inline-block">
          <Image
            src="/logo-color-light.svg"
            alt="Chiripa"
            width={140}
            height={36}
            priority
          />
        </Link>
      </div>

      <div className="mb-3 px-1">
        <WorkspaceSelector />
      </div>

      <nav className="flex flex-col gap-1" aria-label="Navegación principal">
        {navItems.map((item) => (
          <NavItem
            key={item.href}
            icon={item.icon}
            label={item.label}
            href={item.href}
            active={isActive(pathname, item.href)}
            // Alertas lleva contador de avisos no leídos + invitaciones pendientes
            badge={item.href === "/alertas" ? totalNotifications : undefined}
          />
        ))}
      </nav>

      <div className="flex-1" />

      <div className="mt-auto pt-4 border-t border-border-subtle flex items-center gap-3 group">
        <Avatar name={currentUser.name} size="md" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-text-strong truncate">
            {currentUser.name}
          </div>
          <div className="text-xs text-text-subtle truncate">
            {currentUser.company}
          </div>
        </div>
        <Link
          href="/configuracion/notificaciones"
          className="p-1.5 rounded-md text-text-subtle hover:bg-warm-100 hover:text-text-strong transition-all duration-200"
          title="Preferencias de alertas"
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
  );
}
