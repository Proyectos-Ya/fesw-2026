"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { Avatar } from "./Avatar";

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

interface SidebarProps {
  user?: {
    name: string;
    company?: string;
    avatar?: string;
  };
}

export function Sidebar({ user }: SidebarProps) {
  const pathname = usePathname();

  const currentUser = user ?? {
    name: "Usuario Demo",
    company: "Empresa Demo S.A.",
  };

  return (
    <aside className="w-64 flex-none bg-white border-r border-border-subtle flex flex-col p-4 gap-1 sticky top-0 h-screen shadow-xs">
      <div className="px-2 py-4 mb-4">
        <Link href="/" className="inline-block">
          <span className="font-display text-xl font-bold tracking-tight text-text-strong">
            ProyectosYa
          </span>
        </Link>
      </div>

      <div className="flex-1" />

      <div className="mt-auto pt-4 border-t border-border-subtle flex items-center gap-3 group">
        <Avatar name={currentUser.name} src={currentUser.avatar} size="md" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-text-strong truncate">
            {currentUser.name}
          </div>
          <div className="text-xs text-text-subtle truncate">
            {currentUser.company}
          </div>
        </div>
        <Link 
          href="/perfil"
          className="p-1.5 rounded-md text-text-subtle hover:bg-primary-soft hover:text-primary transition-all duration-200"
          title="Configuración de perfil"
        >
          <Icon name="settings" size={18} />
        </Link>
      </div>
    </aside>
  );
}
