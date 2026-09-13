"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Icon } from "@/features/shared/components/Icon";
import { Avatar } from "@/features/shared/components/Avatar";
import { useWorkspace } from "../WorkspaceContext";
import { InviteMemberModal } from "./InviteMemberModal";
import type { MemberRole } from "../types";

export function getRoleBadge(role: MemberRole) {
  switch (role) {
    case "admin":
      return {
        label: "Admin",
        className: "bg-purple-100 text-purple-700 border-purple-200",
      };
    case "member":
      return {
        label: "Miembro",
        className: "bg-blue-100 text-blue-700 border-blue-200",
      };
    case "viewer":
      return {
        label: "Lector",
        className: "bg-gray-100 text-gray-700 border-gray-200",
      };
  }
}

export function WorkspaceSelector() {
  const {
    workspaces,
    activeWorkspace,
    switchActiveWorkspace,
    isLoading,
  } = useWorkspace();
  const [isOpen, setIsOpen] = useState(false);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 p-2 rounded-lg border border-border-subtle bg-white animate-pulse">
        <div className="size-8 rounded-md bg-warm-200" />
        <div className="flex-1 space-y-1">
          <div className="h-3 w-24 rounded bg-warm-200" />
          <div className="h-2 w-16 rounded bg-warm-200" />
        </div>
      </div>
    );
  }

  if (workspaces.length === 0) {
    return (
      <Link
        href="/empresa/crear"
        className="flex items-center gap-3 p-2 rounded-lg border border-dashed border-primary/40 bg-primary-soft/30 text-primary hover:bg-primary-soft hover:border-primary transition-colors group"
      >
        <div className="flex size-8 items-center justify-center rounded-md bg-primary-soft text-primary group-hover:scale-105 transition-transform">
          <Icon name="plus" size={16} />
        </div>
        <div className="text-xs font-bold truncate">Registrar empresa</div>
      </Link>
    );
  }

  const currentWorkspaceSummary = workspaces.find(
    (w) => w.supplier_id === activeWorkspace?.active_supplier_id,
  ) ?? workspaces[0];

  const roleBadge = getRoleBadge(
    activeWorkspace?.role ?? currentWorkspaceSummary.role,
  );

  const handleSelectWorkspace = async (supplierId: string) => {
    if (supplierId === activeWorkspace?.active_supplier_id) {
      setIsOpen(false);
      return;
    }
    setIsSwitching(true);
    try {
      await switchActiveWorkspace(supplierId);
    } finally {
      setIsSwitching(false);
      setIsOpen(false);
    }
  };

  return (
    <>
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="flex w-full items-center gap-2.5 rounded-lg border border-border-subtle bg-white p-2 text-left hover:border-border-strong hover:shadow-2xs transition-all cursor-pointer group"
          aria-expanded={isOpen}
          aria-haspopup="true"
          aria-label="Seleccionar espacio de trabajo"
        >
          <Avatar
            name={currentWorkspaceSummary.trade_name || currentWorkspaceSummary.legal_name}
            size="sm"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-text-strong truncate">
                {currentWorkspaceSummary.trade_name || currentWorkspaceSummary.legal_name}
              </span>
              <span
                className={`inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold border ${roleBadge.className}`}
              >
                {roleBadge.label}
              </span>
            </div>
            <p className="text-[11px] text-text-subtle truncate">
              {currentWorkspaceSummary.rut}
            </p>
          </div>
          <Icon
            name="chevron-down"
            size={16}
            className={`text-text-subtle group-hover:text-text-strong transition-transform duration-200 ${
              isOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        {isOpen && (
          <div className="absolute top-full left-0 mt-1.5 w-full min-w-[240px] rounded-xl border border-border-subtle bg-white p-1.5 shadow-lg z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-subtle border-b border-border-subtle mb-1">
              Espacios de trabajo
            </div>

            <div className="max-h-56 overflow-y-auto space-y-0.5">
              {workspaces.map((w) => {
                const isCurrent = w.supplier_id === activeWorkspace?.active_supplier_id;
                const badge = getRoleBadge(w.role);
                return (
                  <button
                    key={w.supplier_id}
                    type="button"
                    onClick={() => void handleSelectWorkspace(w.supplier_id)}
                    disabled={isSwitching}
                    className={`flex w-full items-center gap-2.5 rounded-lg p-2 text-left transition-colors cursor-pointer ${
                      isCurrent
                        ? "bg-primary-soft text-primary font-medium"
                        : "hover:bg-warm-100 text-text-strong"
                    }`}
                  >
                    <Avatar name={w.trade_name || w.legal_name} size="xs" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-semibold truncate">
                          {w.trade_name || w.legal_name}
                        </span>
                        <span
                          className={`inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-semibold border ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </div>
                      <p className="text-[10px] text-text-subtle truncate">{w.rut}</p>
                    </div>
                    {isCurrent && (
                      <Icon name="check" size={14} className="text-primary flex-none" />
                    )}
                  </button>
                );
              })}
            </div>

            <div className="mt-1 pt-1 border-t border-border-subtle space-y-0.5">
              {activeWorkspace?.is_admin && (
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false);
                    setIsInviteModalOpen(true);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg p-2 text-xs font-semibold text-text-strong hover:bg-warm-100 hover:text-primary transition-colors cursor-pointer"
                >
                  <Icon name="user-plus" size={15} />
                  <span>Invitar miembro</span>
                </button>
              )}

              <Link
                href="/empresa/crear"
                onClick={() => setIsOpen(false)}
                className="flex w-full items-center gap-2 rounded-lg p-2 text-xs font-semibold text-text-strong hover:bg-warm-100 hover:text-primary transition-colors"
              >
                <Icon name="plus" size={15} />
                <span>Registrar nueva empresa</span>
              </Link>
            </div>
          </div>
        )}
      </div>

      {activeWorkspace && (
        <InviteMemberModal
          isOpen={isInviteModalOpen}
          onClose={() => setIsInviteModalOpen(false)}
          supplierId={activeWorkspace.active_supplier_id}
          supplierName={activeWorkspace.active_supplier_name}
        />
      )}
    </>
  );
}
