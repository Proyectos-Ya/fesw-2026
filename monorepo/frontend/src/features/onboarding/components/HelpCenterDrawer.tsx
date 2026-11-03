"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
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

export function getTourConfigForPath(pathname: string) {
  if (
    pathname.includes("/postulacion") ||
    pathname.includes("/cotizacion") ||
    pathname.includes("/propuesta")
  ) {
    return {
      type: "draft" as const,
      title: "Tour de Postulación",
      description:
        "Revisa cómo preparar y organizar tu propuesta, adjuntar evidencias y afinar tu cotización con IA.",
      buttonText: "Reiniciar tour de postulación",
    };
  }

  if (pathname.includes("/matches/")) {
    return {
      type: "detail" as const,
      title: "Tour de Licitación",
      description:
        "Aprende a analizar los requisitos, desglosar las bases y consultar dudas con el Asistente de IA.",
      buttonText: "Reiniciar tour de licitación",
    };
  }

  return {
    type: "home" as const,
    title: "Tour de Inicio",
    description:
      "Vuelve a revisar tus recomendaciones automáticas, el buscador manual y el estado de tus licitaciones.",
    buttonText: "Reiniciar tour de inicio",
  };
}

export function HelpCenterDrawer() {
  const pathname = usePathname();
  const router = useRouter();

  const isHelpCenterOpen = useOnboardingStore(
    (state) => state.isHelpCenterOpen,
  );
  const closeHelpCenter = useOnboardingStore((state) => state.closeHelpCenter);
  const resetTour = useOnboardingStore((state) => state.resetTour);

  const tourConfig = getTourConfigForPath(pathname || "/");

  const handleResetTour = () => {
    if (tourConfig.type === "home" && pathname !== "/") {
      router.push("/");
    }
    resetTour(tourConfig.type);
  };

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
          {/* Tarjeta destacada dinámica: Reiniciar Tour */}
          <div className="rounded-xl border border-primary-border bg-primary-soft/60 p-5 shadow-xs">
            <div className="flex items-start gap-3">
              <div className="flex size-9 flex-none items-center justify-center rounded-full bg-primary text-on-primary">
                <Icon name="sparkles" size={18} />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-text-strong">
                  {tourConfig.title}
                </h3>
                <p className="text-xs text-text-muted leading-relaxed">
                  {tourConfig.description}
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Button
                type="button"
                variant="primary"
                onClick={handleResetTour}
                className="w-full"
              >
                <Icon name="rotate-ccw" size={16} />
                {tourConfig.buttonText}
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
