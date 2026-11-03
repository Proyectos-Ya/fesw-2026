"use client";

import { useEffect } from "react";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useOnboardingStore } from "../store/useOnboardingStore";

interface HelpGuideSection {
  id: string;
  icon: string;
  title: string;
  description: string;
}

const HELP_GUIDES: ReadonlyArray<HelpGuideSection> = [
  {
    id: "matching",
    icon: "target",
    title: "Cómo funciona el matching",
    description:
      "Cruzamos semánticamente las licitaciones de Mercado Público con el rubro, regiones y experiencia de tu empresa para calcular un porcentaje de compatibilidad y priorizar tus mejores oportunidades del día.",
  },
  {
    id: "search",
    icon: "search",
    title: "Búsqueda manual",
    description:
      "En la sección Buscar puedes explorar todo el catálogo de compras públicas filtrando por palabras clave, región, comuna, estado y rango de presupuesto.",
  },
  {
    id: "kanban",
    icon: "kanban",
    title: "Guardados y Tablero Kanban",
    description:
      "Guarda las licitaciones de tu interés y organízalas por etapas en el Tablero Kanban para coordinar la preparación de ofertas junto a tu equipo.",
  },
  {
    id: "alerts",
    icon: "bell",
    title: "Alertas y notificaciones",
    description:
      "Configura tus preferencias en Alertas para recibir avisos oportunos cuando se publiquen nuevas licitaciones compatibles o se acerquen fechas de cierre.",
  },
];

export function HelpCenterDrawer() {
  const isHelpCenterOpen = useOnboardingStore(
    (state) => state.isHelpCenterOpen,
  );
  const closeHelpCenter = useOnboardingStore((state) => state.closeHelpCenter);
  const resetTour = useOnboardingStore((state) => state.resetTour);

  useEffect(() => {
    if (!isHelpCenterOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeHelpCenter();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isHelpCenterOpen, closeHelpCenter]);

  if (!isHelpCenterOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
        onClick={closeHelpCenter}
        aria-hidden="true"
      />

      {/* Drawer lateral derecho */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-center-title"
        className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-border-subtle bg-surface-card shadow-lg"
      >
        {/* Encabezado */}
        <div className="flex items-center justify-between border-b border-border-subtle px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary-soft text-primary">
              <Icon name="book-open" size={18} />
            </div>
            <h2
              id="help-center-title"
              className="font-display text-lg font-bold text-text-strong"
            >
              Centro de Ayuda
            </h2>
          </div>
          <button
            type="button"
            onClick={closeHelpCenter}
            aria-label="Cerrar centro de ayuda"
            className="rounded-lg p-1.5 text-text-subtle hover:bg-surface-hover hover:text-text-strong transition-colors"
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        {/* Contenido desplazable */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Tarjeta destacada: Reiniciar Tour */}
          <div className="rounded-xl border border-primary-border bg-primary-soft/60 p-5 shadow-xs">
            <div className="flex items-start gap-3">
              <div className="flex size-9 flex-none items-center justify-center rounded-full bg-primary text-on-primary">
                <Icon name="sparkles" size={18} />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-text-strong">
                  Recorrido guiado de Chiripa
                </h3>
                <p className="text-xs text-text-muted leading-relaxed">
                  Vuelve a revisar paso a paso dónde encontrar tus matches
                  automáticos, el buscador manual y el análisis con IA.
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Button
                type="button"
                variant="primary"
                onClick={resetTour}
                className="w-full"
              >
                <Icon name="rotate-ccw" size={16} />
                Reiniciar tour interactivo
              </Button>
            </div>
          </div>

          {/* Guías estáticas */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Guías rápidas de la plataforma
            </h3>
            <div className="space-y-3">
              {HELP_GUIDES.map((guide) => (
                <article
                  key={guide.id}
                  className="rounded-lg border border-border-subtle bg-surface-inset/50 p-4 transition-colors hover:border-border-default"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 flex size-7 flex-none items-center justify-center rounded-md bg-surface-card text-primary shadow-xs">
                      <Icon name={guide.icon} size={16} />
                    </div>
                    <div className="space-y-1">
                      <h4 className="text-sm font-bold text-text-strong">
                        {guide.title}
                      </h4>
                      <p className="text-xs text-text-muted leading-relaxed">
                        {guide.description}
                      </p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
