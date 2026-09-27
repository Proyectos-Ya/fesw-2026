"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useWorkspace } from "@/features/workspaces/WorkspaceContext";
import {
  cancelInvitation,
  createInvitation,
  listWorkspaceInvitations,
  listWorkspaceMembers,
} from "@/features/workspaces/services/workspaceService";
import type {
  MemberRole,
  SupplierInvitation,
  WorkspaceMemberDetail,
} from "@/features/workspaces/types";

interface CompanyTeamSectionProps {
  supplierId: string;
  supplierName: string;
}

function formatRoleLabel(role: MemberRole): string {
  if (role === "admin") return "Administrador";
  return "Miembro";
}

export function CompanyTeamSection({
  supplierId,
  supplierName,
}: CompanyTeamSectionProps) {
  const { isAdmin } = useWorkspace();
  const [members, setMembers] = useState<WorkspaceMemberDetail[]>([]);
  const [pendingInvitations, setPendingInvitations] = useState<
    SupplierInvitation[]
  >([]);
  const [isLoadingTeam, setIsLoadingTeam] = useState(false);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const [invitationToCancel, setInvitationToCancel] =
    useState<SupplierInvitation | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);

  const loadTeamData = useCallback(async () => {
    if (!supplierId) return;
    setIsLoadingTeam(true);
    try {
      if (isAdmin) {
        const [membersRes, invitationsRes] = await Promise.allSettled([
          listWorkspaceMembers(supplierId),
          listWorkspaceInvitations(supplierId),
        ]);
        if (membersRes.status === "fulfilled") {
          setMembers(membersRes.value);
        }
        if (invitationsRes.status === "fulfilled") {
          setPendingInvitations(invitationsRes.value);
        }
      } else {
        const membersList = await listWorkspaceMembers(supplierId);
        setMembers(membersList);
      }
    } catch {
      // Silencia error de carga inicial para no romper la vista de empresa
    } finally {
      setIsLoadingTeam(false);
    }
  }, [isAdmin, supplierId]);

  useEffect(() => {
    void loadTeamData();
  }, [loadTeamData]);

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setFeedbackMessage(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setFormError("Por favor ingresa un correo electrónico válido.");
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await createInvitation({
        supplier_id: supplierId,
        email: trimmedEmail,
        role,
      });
      setPendingInvitations((prev) => [
        created,
        ...prev.filter((item) => item.id !== created.id),
      ]);
      setEmail("");
      setRole("member");
      setFeedbackMessage(
        `Invitación enviada a ${created.email}. Se ha despachado un correo electrónico con las instrucciones.`,
      );
    } catch (err: unknown) {
      if (err instanceof ApiError || err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo enviar la invitación. Inténtalo nuevamente.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!invitationToCancel) return;
    setIsCancelling(true);
    setFormError(null);
    setFeedbackMessage(null);

    try {
      await cancelInvitation(invitationToCancel.id);
      setPendingInvitations((prev) =>
        prev.filter((item) => item.id !== invitationToCancel.id),
      );
      setInvitationToCancel(null);
      setFeedbackMessage("Invitación cancelada correctamente.");
    } catch (err: unknown) {
      if (err instanceof ApiError || err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo cancelar la invitación.");
      }
      setInvitationToCancel(null);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleAcknowledgeRejected = async (invitation: SupplierInvitation) => {
    setAcknowledgingId(invitation.id);
    setFormError(null);
    setFeedbackMessage(null);

    try {
      await cancelInvitation(invitation.id);
      setPendingInvitations((prev) =>
        prev.filter((item) => item.id !== invitation.id),
      );
    } catch (err: unknown) {
      if (err instanceof ApiError || err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo confirmar la lectura de la invitación.");
      }
    } finally {
      setAcknowledgingId(null);
    }
  };

  return (
    <section className="mt-8 rounded-lg bg-white p-8 shadow-premium border border-border-subtle flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-strong">
            Equipo de la empresa
          </h2>
          <p className="text-sm text-text-muted mt-1">
            {isAdmin
              ? `Gestiona los representantes activos y las invitaciones pendientes de ${supplierName}.`
              : `Integrantes activos de ${supplierName}.`}
          </p>
        </div>
      </div>

      {/* Formulario de invitación exclusivo para Administradores (CA1, CA2, CA3) */}
      {isAdmin && (
        <form
          onSubmit={(e) => void handleInviteSubmit(e)}
          className="rounded-lg border border-border-subtle bg-surface-base/50 p-4 flex flex-col gap-4"
          noValidate
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-12 sm:items-end">
            <div className="sm:col-span-6">
              <label
                htmlFor="invite-member-email"
                className="block text-xs font-bold uppercase tracking-caps text-text-subtle mb-1.5"
              >
                Correo electrónico del invitado
              </label>
              <input
                id="invite-member-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="representante@empresa.cl"
                disabled={isSubmitting}
                className="w-full rounded-lg border border-border-subtle bg-white px-3.5 py-2 text-sm text-text-strong placeholder:text-text-subtle focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
              />
            </div>

            <div className="sm:col-span-3">
              <label
                htmlFor="invite-member-role"
                className="block text-xs font-bold uppercase tracking-caps text-text-subtle mb-1.5"
              >
                Rol asignado
              </label>
              <select
                id="invite-member-role"
                value={role}
                onChange={(e) => setRole(e.target.value as MemberRole)}
                disabled={isSubmitting}
                className="w-full rounded-lg border border-border-subtle bg-white px-3 py-2 text-sm text-text-strong focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
              >
                <option value="member">Miembro</option>
                <option value="admin">Administrador</option>
              </select>
            </div>

            <div className="sm:col-span-3">
              <Button
                type="submit"
                variant="primary"
                isLoading={isSubmitting}
                className="w-full font-bold"
              >
                Enviar invitación
              </Button>
            </div>
          </div>

          {formError && (
            <div
              role="alert"
              className="flex items-center gap-2 rounded-lg bg-danger-soft/40 border border-danger/20 p-3 text-xs font-medium text-danger"
            >
              <Icon name="circle-alert" size={16} />
              <span>{formError}</span>
            </div>
          )}

          {feedbackMessage && (
            <div
              role="status"
              className="flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-xs font-medium text-emerald-700"
            >
              <Icon name="circle-check" size={16} />
              <span>{feedbackMessage}</span>
            </div>
          )}
        </form>
      )}

      {/* Tabla de miembros actuales (visible para Administradores y Miembros) */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-caps text-text-subtle mb-3">
          Miembros actuales ({members.length})
        </h3>
        {isLoadingTeam && members.length === 0 ? (
          <p className="text-xs text-text-muted">Cargando equipo...</p>
        ) : members.length === 0 ? (
          <p className="text-sm text-text-subtle">
            No se encontraron miembros registrados.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border-subtle">
            <table className="w-full text-left text-sm">
              <thead className="bg-warm-100/60 text-xs font-bold uppercase text-text-subtle border-b border-border-subtle">
                <tr>
                  <th className="px-4 py-2.5">Nombre</th>
                  <th className="px-4 py-2.5">Correo</th>
                  <th className="px-4 py-2.5">Rol</th>
                  <th className="px-4 py-2.5">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {members.map((member) => (
                  <tr key={member.id}>
                    <td className="px-4 py-3 font-medium text-text-strong">
                      {member.full_name}
                    </td>
                    <td className="px-4 py-3 text-text-muted">
                      {member.email}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-semibold text-primary">
                        {formatRoleLabel(member.role)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                        Activo
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Tabla de invitaciones pendientes y rechazadas (exclusiva para Administradores) */}
      {isAdmin && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-caps text-text-subtle mb-3">
            Invitaciones pendientes ({pendingInvitations.length})
          </h3>
          {pendingInvitations.length === 0 ? (
            <p className="text-sm text-text-subtle">
              No hay invitaciones pendientes en este momento.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border-subtle">
              <table className="w-full text-left text-sm">
                <thead className="bg-warm-100/60 text-xs font-bold uppercase text-text-subtle border-b border-border-subtle">
                  <tr>
                    <th className="px-4 py-2.5">Correo invitado</th>
                    <th className="px-4 py-2.5">Rol</th>
                    <th className="px-4 py-2.5">Estado</th>
                    <th className="px-4 py-2.5 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {pendingInvitations.map((inv) => {
                    const isRejected = inv.status === "rejected";
                    return (
                      <tr key={inv.id}>
                        <td className="px-4 py-3 font-medium text-text-strong">
                          {inv.email}
                        </td>
                        <td className="px-4 py-3 text-text-muted">
                          {formatRoleLabel(inv.role)}
                        </td>
                        <td className="px-4 py-3">
                          {isRejected ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-danger-soft/60 px-2.5 py-0.5 text-xs font-semibold text-danger">
                              El usuario rechazó la invitación
                            </span>
                          ) : (
                            <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
                              Pendiente
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {isRejected ? (
                            <button
                              type="button"
                              aria-label={`Confirmar lectura de ${inv.email}`}
                              disabled={acknowledgingId === inv.id}
                              onClick={() =>
                                void handleAcknowledgeRejected(inv)
                              }
                              className="inline-flex items-center gap-1 rounded-md bg-warm-100 px-2.5 py-1 text-xs font-semibold text-text-strong hover:bg-warm-200 transition-colors cursor-pointer disabled:opacity-50"
                            >
                              <Icon name="check" size={14} />
                              <span>Confirmar lectura</span>
                            </button>
                          ) : (
                            <button
                              type="button"
                              aria-label={`Cancelar invitación de ${inv.email}`}
                              onClick={() => setInvitationToCancel(inv)}
                              className="inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold text-danger hover:bg-danger-soft/40 transition-colors cursor-pointer"
                            >
                              <Icon name="x" size={14} />
                              <span>Cancelar</span>
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Diálogo de confirmación de cancelación (CA7) */}
      {isAdmin && invitationToCancel && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="cancel-invitation-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl border border-border-subtle">
            <h4
              id="cancel-invitation-title"
              className="text-base font-bold text-text-strong"
            >
              ¿Cancelar invitación pendiente?
            </h4>
            <p className="mt-2 text-sm text-text-muted">
              La invitación enviada a{" "}
              <span className="font-semibold text-text-strong">
                {invitationToCancel.email}
              </span>{" "}
              quedará invalidada de inmediato y ya no podrá ser aceptada.
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setInvitationToCancel(null)}
                disabled={isCancelling}
              >
                Volver
              </Button>
              <Button
                type="button"
                variant="primary"
                isLoading={isCancelling}
                onClick={() => void handleConfirmCancel()}
                className="bg-danger hover:bg-danger/90 font-bold"
              >
                Confirmar cancelación
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
