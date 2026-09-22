"use client";

import { useRouter } from "next/navigation";
import { Icon } from "./Icon";

interface BackLinkProps {
  /** A dónde ir cuando no hay historial: enlace abierto desde un correo, o pestaña nueva. */
  fallbackHref: string;
  children: React.ReactNode;
  id?: string;
}

/**
 * Flecha de "volver" que respeta de dónde vino el usuario.
 *
 * Un `href` fijo obliga a un solo destino, y a la misma ficha de licitación se
 * llega desde el buscador, desde los matches, desde las guardadas y desde una
 * alerta. Mandar a todos al dashboard descarta la búsqueda que el usuario
 * acababa de hacer.
 */
export function BackLink({ fallbackHref, children, id }: BackLinkProps) {
  const router = useRouter();

  const volver = () => {
    // `length > 1` significa que esta pestaña tiene una entrada anterior. Si no
    // la hay —el enlace se abrió directo— retroceder no haría nada y el usuario
    // se quedaría encerrado en la ficha.
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push(fallbackHref);
  };

  return (
    <button
      type="button"
      onClick={volver}
      id={id}
      className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-text-muted hover:text-primary transition-colors cursor-pointer"
    >
      <Icon name="arrow-left" size={14} />
      {children}
    </button>
  );
}
