"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/features/shared/components/Icon";
import { Avatar } from "@/features/shared/components/Avatar";
import { useWorkspace } from "../WorkspaceContext";
import { getRoleBadge } from "./WorkspaceSelector";
import { PendingInvitationsList } from "./PendingInvitationsList";

export function WorkspaceSelectionScreen() {
  const router = useRouter();
  const { workspaces, activeWorkspace, switchActiveWorkspace, isLoading } = useWorkspace();
  const [isSwitching, setIsSwitching] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const handleSelect = async (supplierId: string) => {
    setSelectedId(supplierId);
    setIsSwitching(true);
    try {
      await switchActiveWorkspace(supplierId);
      router.push("/");
    } finally {
      setIsSwitching(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 text-text-muted">
          <span className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span>Cargando tus espacios de trabajo...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl py-8 px-4">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-2xl bg-primary-soft text-primary shadow-xs">
          <Icon name="building-2" size={24} />
        </div>
        <h1 className="text-2xl font-bold text-text-strong">
          Selecciona tu espacio de trabajo
        </h1>
        <p className="mt-1.5 text-sm text-text-muted">
          Elige la empresa con la que deseas operar y gestionar licitaciones en esta sesión.
        </p>
      </div>

      <PendingInvitationsList />

      <div className="space-y-3">
        {workspaces.map((w) => {
          const isCurrent = w.supplier_id === activeWorkspace?.active_supplier_id;
          const badge = getRoleBadge(w.role);
          const isBeingSelected = isSwitching && selectedId === w.supplier_id;

          return (
            <div
              key={w.supplier_id}
              onClick={() => !isSwitching && void handleSelect(w.supplier_id)}
              className={`group flex items-center justify-between rounded-xl border p-4 transition-all duration-200 cursor-pointer ${
                isCurrent
                  ? "border-primary/50 bg-primary-soft/10 shadow-xs ring-1 ring-primary/20"
                  : "border-border-subtle bg-surface-card hover:border-border-strong hover:shadow-sm"
              }`}
            >
              <div className="flex items-center gap-4 min-w-0">
                <Avatar name={w.trade_name || w.legal_name} size="lg" />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-text-strong truncate group-hover:text-primary transition-colors">
                      {w.trade_name || w.legal_name}
                    </h2>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${badge.className}`}
                    >
                      {badge.label}
                    </span>
                  </div>
                  <p className="text-xs text-text-subtle">{w.rut}</p>
                  {w.trade_name && (
                    <p className="text-xs text-text-muted truncate mt-0.5">
                      {w.legal_name}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {isBeingSelected ? (
                  <span className="size-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                ) : isCurrent ? (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-primary">
                    <Icon name="check" size={16} />
                    <span>Activo</span>
                  </span>
                ) : (
                  <span className="p-2 rounded-lg text-text-subtle group-hover:bg-warm-100 group-hover:text-text-strong transition-colors">
                    <Icon name="chevron-right" size={20} />
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-8 pt-6 border-t border-border-subtle flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-xs text-text-subtle text-center sm:text-left">
          ¿Trabajas con otra empresa o necesitas crear un nuevo perfil corporativo?
        </p>
        <Link
          href="/empresa/crear"
          className="inline-flex items-center gap-2 rounded-lg bg-white border border-border-subtle px-4 py-2.5 text-xs font-semibold text-text-strong hover:border-primary hover:text-primary transition-colors shadow-2xs whitespace-nowrap"
        >
          <Icon name="plus" size={15} />
          <span>Registrar nueva empresa</span>
        </Link>
      </div>
    </div>
  );
}
