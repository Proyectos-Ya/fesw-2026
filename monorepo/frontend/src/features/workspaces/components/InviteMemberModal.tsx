"use client";

import React, { useState } from "react";
import { Icon } from "@/features/shared/components/Icon";
import { createInvitation } from "../services/workspaceService";
import type { MemberRole } from "../types";

interface InviteMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  supplierId: string;
  supplierName: string;
  onSuccess?: () => void;
}

export function InviteMemberModal({
  isOpen,
  onClose,
  supplierId,
  supplierName,
  onSuccess,
}: InviteMemberModalProps) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MemberRole>("member");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!email.trim() || !email.includes("@")) {
      setError("Por favor ingresa un correo electrónico válido.");
      return;
    }

    setIsLoading(true);
    try {
      await createInvitation({
        supplier_id: supplierId,
        email: email.trim().toLowerCase(),
        role,
      });
      setSuccessMessage(
        `Invitación enviada con éxito a ${email}. El usuario verá la notificación al ingresar a Chiripa.`,
      );
      setEmail("");
      if (onSuccess) onSuccess();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Ocurrió un error al enviar la invitación.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="invite-modal-title"
    >
      <div className="w-full max-w-md rounded-xl bg-surface-card p-6 shadow-xl border border-border-subtle">
        <div className="flex items-center justify-between pb-4 border-b border-border-subtle">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <Icon name="user-plus" size={20} />
            </div>
            <div>
              <h2 id="invite-modal-title" className="text-base font-bold text-text-strong">
                Invitar miembro
              </h2>
              <p className="text-xs text-text-subtle truncate max-w-[260px]">
                {supplierName}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar modal"
            className="rounded-lg p-1.5 text-text-subtle hover:bg-warm-100 hover:text-text-strong transition-colors cursor-pointer"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        {successMessage ? (
          <div className="py-6 text-center space-y-4">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <Icon name="check" size={24} />
            </div>
            <p className="text-sm text-text-strong">{successMessage}</p>
            <button
              type="button"
              onClick={() => {
                setSuccessMessage(null);
                onClose();
              }}
              className="w-full rounded-lg bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover transition-colors cursor-pointer"
            >
              Aceptar
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="mt-4 space-y-4">
            {error && (
              <div className="rounded-lg bg-danger-soft p-3 text-xs text-danger flex items-start gap-2">
                <Icon name="alert-circle" size={16} className="mt-0.5 flex-none" />
                <span>{error}</span>
              </div>
            )}

            <div>
              <label
                htmlFor="invite-email"
                className="block text-xs font-semibold text-text-strong mb-1.5"
              >
                Correo electrónico del usuario
              </label>
              <input
                id="invite-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ejemplo@empresa.cl"
                className="w-full rounded-lg border border-border-subtle bg-white px-3.5 py-2.5 text-sm text-text-strong placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
              <p className="mt-1 text-[11px] text-text-subtle">
                El usuario recibirá una notificación directa dentro de su cuenta en Chiripa.
              </p>
            </div>

            <div>
              <label
                htmlFor="invite-role"
                className="block text-xs font-semibold text-text-strong mb-1.5"
              >
                Rol asignado
              </label>
              <select
                id="invite-role"
                value={role}
                onChange={(e) => setRole(e.target.value as MemberRole)}
                className="w-full rounded-lg border border-border-subtle bg-white px-3.5 py-2.5 text-sm text-text-strong focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              >
                <option value="member">Miembro (Visualización y postulación)</option>
                <option value="admin">Administrador (Gestión total y miembros)</option>
                <option value="viewer">Lector (Solo lectura)</option>
              </select>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="flex-1 rounded-lg border border-border-subtle bg-white py-2.5 text-sm font-medium text-text-muted hover:bg-warm-100 hover:text-text-strong transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover transition-colors disabled:opacity-50 cursor-pointer"
              >
                {isLoading ? "Enviando..." : "Invitar miembro"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
