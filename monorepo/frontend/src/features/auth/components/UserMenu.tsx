"use client";

import { useState } from "react";
import { useSession } from "./SessionProvider";
import { Avatar } from "@/features/shared/components/Avatar";
import { Icon } from "@/features/shared/components/Icon";

/** Avatar del usuario en el header con menú desplegable (perfil + logout). */
export function UserMenu() {
  const { user, logout } = useSession();
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="rounded-full transition-all hover:ring-2 hover:ring-primary/30"
        title={user?.full_name ?? "Mi cuenta"}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Avatar name={user?.full_name ?? ""} size="md" />
      </button>

      {open && (
        <>
          {/* Captura el clic fuera del menú para cerrarlo */}
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            role="menu"
            className="absolute right-0 top-full z-20 mt-2 w-64 rounded-lg border border-border-subtle bg-white p-2 shadow-premium"
          >
            <div className="px-3 py-2 border-b border-border-subtle mb-1">
              <div className="text-sm font-bold text-text-strong truncate">
                {user?.full_name}
              </div>
              <div className="text-xs text-text-subtle truncate">
                {user?.email}
              </div>
            </div>
            <button
              type="button"
              role="menuitem"
              onClick={() => void logout()}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold text-text-muted transition-colors hover:bg-danger-soft hover:text-danger"
            >
              <Icon name="log-out" size={16} />
              Cerrar sesión
            </button>
          </div>
        </>
      )}
    </div>
  );
}
