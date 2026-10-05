"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/features/shared/components/Icon";
import { useWorkspace } from "../WorkspaceContext";

export function GlobalInvitationsBanner() {
  const pathname = usePathname() ?? "";
  const { invitations } = useWorkspace();

  if (!invitations || invitations.length === 0) {
    return null;
  }

  // En la pantalla dedicada /workspaces ya se muestra la lista completa
  if (pathname === "/workspaces") {
    return null;
  }

  const count = invitations.length;
  const firstInvitation = invitations[0];
  const targetCompany = firstInvitation?.supplier_name
    ? firstInvitation.supplier_name
    : "un espacio de trabajo";

  return (
    <aside
      aria-label="Aviso de invitaciones pendientes"
      className="bg-primary-soft/90 border-b border-primary/20 px-6 py-2.5 transition-all flex items-center justify-between gap-4"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex size-7 flex-none items-center justify-center rounded-full bg-primary text-white shadow-2xs">
          <Icon name="mail" size={14} />
        </div>
        <p className="text-xs sm:text-sm font-medium text-text-strong truncate">
          {count === 1 ? (
            <>
              Tienes una invitación pendiente para unirte a{" "}
              <strong className="font-bold text-text-strong">{targetCompany}</strong>.
            </>
          ) : (
            <>
              Tienes {count} invitaciones pendientes para unirte a empresas colaboradoras.
            </>
          )}
        </p>
      </div>

      <div className="flex items-center gap-2 flex-none">
        <Link
          href="/workspaces"
          className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover transition-colors shadow-2xs cursor-pointer"
        >
          <span>Revisar invitaciones</span>
          <Icon name="arrow-right" size={13} />
        </Link>
      </div>
    </aside>
  );
}
