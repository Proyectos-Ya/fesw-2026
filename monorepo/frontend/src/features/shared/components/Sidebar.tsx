"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { Avatar } from "./Avatar";
import { useCompany } from "@/features/company-profile/components/CompanyProvider";

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

function CompanyFooter() {
  const { company } = useCompany();

  if (company.status === "loading" || company.status === "error") return null;

  if (company.status === "without-company") {
    return (
      <Link
        href="/empresa/crear"
        className="mt-auto pt-4 border-t border-border-subtle flex items-center gap-3 group text-text-muted hover:text-primary transition-colors"
      >
        <div className="flex size-10 items-center justify-center rounded-full bg-primary-soft">
          <Icon name="building-2" size={20} color="var(--primary)" />
        </div>
        <div className="text-sm font-bold">Crear tu empresa</div>
      </Link>
    );
  }

  const { supplier } = company;
  return (
    <Link
      href="/empresa"
      className="mt-auto pt-4 border-t border-border-subtle flex items-center gap-3 group hover:bg-warm-100 rounded-md transition-colors p-1 -m-1"
      title="Ver mi empresa"
    >
      <Avatar name={supplier.legal_name} size="md" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-bold text-text-strong truncate">
          {supplier.legal_name}
        </div>
        <div className="text-xs text-text-subtle truncate">{supplier.rut}</div>
      </div>
      <span className="p-1.5 rounded-md text-text-subtle group-hover:text-primary transition-colors">
        <Icon name="building-2" size={18} />
      </span>
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();

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

      <CompanyFooter />
    </aside>
  );
}
