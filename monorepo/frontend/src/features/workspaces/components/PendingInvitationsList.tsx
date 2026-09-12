"use client";

import React, { useState } from "react";
import { Icon } from "@/features/shared/components/Icon";
import { useWorkspace } from "../WorkspaceContext";
import type { SupplierInvitation } from "../types";

export function PendingInvitationsList() {
  const { invitations, acceptPendingInvitation, refreshInvitations } = useWorkspace();
  const [acceptingToken, setAcceptingToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    void refreshInvitations();
  }, [refreshInvitations]);

  if (!invitations || invitations.length === 0) return null;

  const handleAccept = async (invitation: SupplierInvitation) => {
    setError(null);
    setAcceptingToken(invitation.token);
    try {
      await acceptPendingInvitation(invitation.token);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("No se pudo aceptar la invitación.");
      }
    } finally {
      setAcceptingToken(null);
    }
  };

  return (
    <div className="rounded-xl border border-primary/20 bg-primary-soft/30 p-4 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex size-7 items-center justify-center rounded-full bg-primary text-white">
          <Icon name="mail" size={14} />
        </div>
        <h3 className="text-sm font-bold text-text-strong">
          Invitaciones a espacios de trabajo ({invitations.length})
        </h3>
      </div>

      {error && (
        <div className="mb-3 rounded-lg bg-danger-soft p-2.5 text-xs text-danger flex items-center gap-2">
          <Icon name="alert-circle" size={14} />
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-2.5">
        {invitations.map((inv) => (
          <div
            key={inv.id}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg bg-white p-3.5 border border-border-subtle shadow-2xs"
          >
            <div className="flex items-start gap-3 min-w-0">
              <div className="flex size-9 flex-none items-center justify-center rounded-lg bg-warm-100 text-text-muted">
                <Icon name="building-2" size={18} />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-text-strong truncate">
                  Invitación para unirte como{" "}
                  <span className="capitalize font-bold text-primary">
                    {inv.role === "admin"
                      ? "Administrador"
                      : inv.role === "member"
                        ? "Miembro"
                        : "Lector"}
                  </span>
                </p>
                <p className="text-xs text-text-subtle">
                  Recibida el {new Date(inv.created_at).toLocaleDateString("es-CL")}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-center">
              <button
                type="button"
                onClick={() => void handleAccept(inv)}
                disabled={acceptingToken === inv.token}
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover transition-colors disabled:opacity-50 cursor-pointer"
              >
                {acceptingToken === inv.token ? (
                  <>
                    <span className="size-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    <span>Aceptando...</span>
                  </>
                ) : (
                  <>
                    <Icon name="check" size={14} />
                    <span>Aceptar invitación</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
