"use client";

import React, { useState } from "react";
import { ApiError } from "@/features/shared/api/client";
import { Icon } from "@/features/shared/components/Icon";
import { useWorkspace } from "../WorkspaceContext";
import type { SupplierInvitation } from "../types";

export function PendingInvitationsList() {
  const {
    invitations,
    workspaces,
    activeWorkspace,
    acceptPendingInvitation,
    rejectPendingInvitation,
    refreshInvitations,
  } = useWorkspace();

  const [processingToken, setProcessingToken] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<
    "accept" | "reject" | null
  >(null);
  const [dismissedIds, setDismissedIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    void refreshInvitations();
  }, [refreshInvitations]);

  const visibleInvitations = (invitations ?? []).filter(
    (inv) => !dismissedIds.includes(inv.id),
  );

  if (visibleInvitations.length === 0 && !error) return null;

  const hasExistingOrganization =
    workspaces.length > 0 || activeWorkspace !== null;

  const handleInvalidationOrError = (
    invitation: SupplierInvitation,
    err: unknown,
    fallbackMsg: string,
  ) => {
    if (err instanceof ApiError) {
      setError(err.message);
      if (err.status === 410 || err.status === 404 || err.status === 409) {
        setDismissedIds((prev) => [...prev, invitation.id]);
        void refreshInvitations();
      }
      return;
    }
    if (err instanceof Error) {
      setError(err.message);
      return;
    }
    setError(fallbackMsg);
  };

  const handleAccept = async (invitation: SupplierInvitation) => {
    setError(null);
    setProcessingToken(invitation.token);
    setProcessingAction("accept");
    try {
      await acceptPendingInvitation(invitation.token);
    } catch (err: unknown) {
      handleInvalidationOrError(
        invitation,
        err,
        "No se pudo aceptar la invitación.",
      );
    } finally {
      setProcessingToken(null);
      setProcessingAction(null);
    }
  };

  const handleReject = async (invitation: SupplierInvitation) => {
    setError(null);
    setProcessingToken(invitation.token);
    setProcessingAction("reject");
    try {
      await rejectPendingInvitation(invitation.token);
    } catch (err: unknown) {
      handleInvalidationOrError(
        invitation,
        err,
        "No se pudo rechazar la invitación.",
      );
    } finally {
      setProcessingToken(null);
      setProcessingAction(null);
    }
  };

  return (
    <div className="rounded-xl border border-primary/20 bg-primary-soft/30 p-4 mb-6">
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-full bg-primary text-white">
            <Icon name="mail" size={14} />
          </div>
          <h3 className="text-sm font-bold text-text-strong">
            Invitaciones a espacios de trabajo ({visibleInvitations.length})
          </h3>
        </div>
      </div>

      {hasExistingOrganization && visibleInvitations.length > 0 && (
        <p className="mb-3 text-xs text-text-muted">
          Puedes unirte a una nueva empresa sin perder tus membresías actuales y
          alternar entre ellas desde el selector de organizaciones.
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-lg bg-danger-soft p-2.5 text-xs text-danger flex items-center justify-between gap-2"
        >
          <div className="flex items-center gap-2">
            <Icon name="circle-alert" size={14} />
            <span>{error}</span>
          </div>
          <button
            type="button"
            aria-label="Cerrar alerta"
            onClick={() => setError(null)}
            className="text-danger/80 hover:text-danger p-0.5 cursor-pointer"
          >
            <Icon name="x" size={14} />
          </button>
        </div>
      )}

      {visibleInvitations.length > 0 && (
        <div className="space-y-2.5">
          {visibleInvitations.map((inv) => {
            const isBusy = processingToken === inv.token;
            return (
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
                      {inv.supplier_name ? (
                        <>
                          Invitación de{" "}
                          <span className="font-bold text-text-strong">
                            {inv.supplier_name}
                          </span>{" "}
                          para unirte como{" "}
                        </>
                      ) : (
                        <>Invitación para unirte como </>
                      )}
                      <span className="capitalize font-bold text-primary">
                        {inv.role === "admin"
                          ? "Administrador"
                          : inv.role === "member"
                            ? "Representante"
                            : "Lector"}
                      </span>
                    </p>
                    <p className="text-xs text-text-subtle">
                      {inv.supplier_rut ? `RUT ${inv.supplier_rut} · ` : ""}
                      Recibida el{" "}
                      {new Date(inv.created_at).toLocaleDateString("es-CL")}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  <button
                    type="button"
                    onClick={() => void handleReject(inv)}
                    disabled={isBusy}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle bg-white px-3 py-1.5 text-xs font-semibold text-text-muted hover:bg-warm-100 hover:text-text-strong transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isBusy && processingAction === "reject" ? (
                      <span>Rechazando...</span>
                    ) : (
                      <>
                        <Icon name="x" size={14} />
                        <span>Rechazar</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => void handleAccept(inv)}
                    disabled={isBusy}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isBusy && processingAction === "accept" ? (
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
            );
          })}
        </div>
      )}
    </div>
  );
}
