"use client";

import { useState } from "react";
import Link from "next/link";
import { useWorkspace } from "../WorkspaceContext";
import { getRoleBadge } from "./WorkspaceSelector";
import { Icon } from "@/features/shared/components/Icon";

export function RecentWorkspacesBar() {
  const { recentWorkspaces, activeWorkspace, switchActiveWorkspace, isLoading } = useWorkspace();
  const [switchingId, setSwitchingId] = useState<string | null>(null);

  if (isLoading || recentWorkspaces.length === 0) {
    return null;
  }

  const handleSwitch = async (supplierId: string) => {
    if (supplierId === activeWorkspace?.active_supplier_id || switchingId) {
      return;
    }
    setSwitchingId(supplierId);
    try {
      await switchActiveWorkspace(supplierId);
    } catch {
      setSwitchingId(null);
    }
  };

  return (
    <div className="mb-6 rounded-xl border border-border-subtle bg-surface-card p-4 shadow-xs">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-text-muted">
          <Icon name="building-2" size={14} className="text-primary" />
          <span>Espacios de trabajo recientes</span>
        </div>
        <Link
          href="/workspaces"
          className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
        >
          <span>Ver todos</span>
          <Icon name="arrow-right" size={12} />
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
        {recentWorkspaces.map((ws) => {
          const isActive = ws.supplier_id === activeWorkspace?.active_supplier_id;
          const isSwitchingThis = switchingId === ws.supplier_id;
          const badge = getRoleBadge(ws.role);
          const displayName = ws.trade_name || ws.legal_name;

          return (
            <button
              key={ws.supplier_id}
              type="button"
              onClick={() => handleSwitch(ws.supplier_id)}
              disabled={Boolean(switchingId)}
              aria-pressed={isActive}
              title={isActive ? "Espacio de trabajo actualmente activo" : `Cambiar a ${displayName}`}
              className={`group relative flex flex-col justify-between rounded-lg p-3 text-left transition-all border ${
                isActive
                  ? "border-primary bg-primary/5 shadow-xs ring-1 ring-primary/30"
                  : "border-border-subtle bg-surface hover:border-primary/40 hover:bg-surface-elevated cursor-pointer"
              }`}
            >
              <div className="flex items-start justify-between gap-2 w-full">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`text-sm font-bold truncate ${
                        isActive ? "text-primary" : "text-text-strong group-hover:text-primary"
                      }`}
                    >
                      {displayName}
                    </span>
                  </div>
                  <span className="text-xs text-text-muted font-mono block mt-0.5">
                    {ws.rut}
                  </span>
                </div>

                {isSwitchingThis ? (
                  <div className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                ) : isActive ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary">
                    <Icon name="circle-check" size={11} />
                    Activo
                  </span>
                ) : null}
              </div>

              <div className="mt-3 flex items-center justify-between text-[11px] pt-2 border-t border-border-subtle/60">
                <span
                  className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${badge.className}`}
                >
                  {badge.label}
                </span>
                {!isActive && (
                  <span className="text-text-subtle group-hover:text-primary text-[11px] font-medium transition-colors flex items-center gap-0.5">
                    Seleccionar
                    <Icon name="arrow-right" size={11} />
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
