"use client";

import { useEffect, useState, type ComponentType, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Building2,
  ChevronDown,
  FileText,
  Map,
  Search,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { useOnboardingStore } from "../store/useOnboardingStore";

export interface HelpCategory {
  id: string;
  title: string;
  icon: LucideIcon;
  matchRoutes: ReadonlyArray<string | RegExp>;
  content: ReactNode | ComponentType;
}

export const HELP_CATEGORIES: ReadonlyArray<HelpCategory> = [
  {
    id: "navigation",
    title: "Navegación por Chiripa",
    icon: Map,
    matchRoutes: ["/", "/buscar", "/guardados", "/tablero", "/alertas"],
    content: (
      <div className="space-y-2">
        <p>
          Explora licitaciones compatibles desde el <strong>Inicio</strong>, usa el{" "}
          <strong>Buscador manual</strong> con filtros avanzados o gestiona tus oportunidades en el{" "}
          <strong>Tablero Kanban</strong>.
        </p>
        <p>
          Configura tus palabras clave y alertas para no perderte oportunidades con fechas de cierre próximas.
        </p>
      </div>
    ),
  },
  {
    id: "profile",
    title: "Mi perfil de empresa",
    icon: Building2,
    matchRoutes: ["/empresa", "/perfil", "/workspaces", "/configuracion"],
    content: (
      <div className="space-y-2">
        <p>
          Configura el rubro, regiones de operación, certificaciones y experiencia de tu empresa.
        </p>
        <p>
          La IA utiliza estos datos para calcular el puntaje de compatibilidad en cada licitación publicada.
        </p>
      </div>
    ),
  },
  {
    id: "detail",
    title: "Vista detallada de licitaciones",
    icon: Search,
    matchRoutes: ["/matches"],
    content: (
      <div className="space-y-2">
        <p>
          Contenido sobre cómo funciona el Match y el análisis de requisitos clave con el Asistente de IA.
        </p>
        <p>
          Revisa bases administrativas, criterios de evaluación y calendario de hitos oficiales de Mercado Público.
        </p>
      </div>
    ),
  },
  {
    id: "draft",
    title: "Borrador y Cotizador",
    icon: FileText,
    matchRoutes: ["/postulacion", "/cotizacion", "/propuesta"],
    content: (
      <div className="space-y-2">
        <p>
          Genera borradores técnicos adaptados a las exigencias de la Compra Ágil y exporta cotizaciones formales.
        </p>
        <p>
          Adjunta evidencias y certificaciones para respaldar tu cumplimiento de requisitos.
        </p>
      </div>
    ),
  },
];

function getRouteMatchScore(routePattern: string | RegExp, pathname: string): number {
  if (routePattern instanceof RegExp) {
    return routePattern.test(pathname) ? 50 : 0;
  }
  if (routePattern === "/") {
    return pathname === "/" ? 100 : 0;
  }
  if (pathname.includes(routePattern)) {
    return routePattern.length;
  }
  return 0;
}

export function getSortedCategories(
  pathname: string,
  categories: ReadonlyArray<HelpCategory> = HELP_CATEGORIES,
): HelpCategory[] {
  let bestCategory: HelpCategory | null = null;
  let highestScore = 0;

  for (const category of categories) {
    for (const route of category.matchRoutes) {
      const score = getRouteMatchScore(route, pathname);
      if (score > highestScore) {
        highestScore = score;
        bestCategory = category;
      }
    }
  }

  const priorityCategory = bestCategory ?? categories[0];
  if (!priorityCategory) return [...categories];

  const others = categories.filter((c) => c.id !== priorityCategory.id);
  return [priorityCategory, ...others];
}

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

  const normalizedPath = pathname || "/";
  const tourConfig = getTourConfigForPath(normalizedPath);
  const sortedCategories = getSortedCategories(normalizedPath);
  const priorityCategory = sortedCategories[0];

  const [openCategoryId, setOpenCategoryId] = useState<string | null>(
    priorityCategory?.id ?? null,
  );

  useEffect(() => {
    if (priorityCategory) {
      setOpenCategoryId(priorityCategory.id);
    }
  }, [normalizedPath, priorityCategory?.id]);

  const handleResetTour = () => {
    if (tourConfig.type === "home" && normalizedPath !== "/") {
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

          {/* Guías contextuales en formato Accordion */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
              Guías de la plataforma
            </h3>
            <div className="space-y-3" role="region" aria-label="Categorías de ayuda">
              {sortedCategories.map((category) => {
                const CategoryIcon = category.icon;
                const isOpen = openCategoryId === category.id;

                return (
                  <details
                    key={category.id}
                    open={isOpen}
                    className="group rounded-lg border border-border-subtle bg-surface-inset/50 transition-colors hover:border-border-default"
                  >
                    <summary
                      onClick={(e) => {
                        e.preventDefault();
                        setOpenCategoryId((prev) =>
                          prev === category.id ? null : category.id,
                        );
                      }}
                      className="flex cursor-pointer list-none items-center justify-between p-4 font-semibold text-text-strong select-none transition-colors hover:bg-surface-hover/50 [&::-webkit-details-marker]:hidden"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex size-7 flex-none items-center justify-center rounded-md bg-surface-card text-primary shadow-xs">
                          <CategoryIcon size={16} />
                        </div>
                        <h4 className="text-sm font-bold text-text-strong">
                          {category.title}
                        </h4>
                      </div>
                      <ChevronDown
                        size={16}
                        className={`text-text-subtle transition-transform duration-200 ${
                          isOpen ? "rotate-180" : ""
                        }`}
                      />
                    </summary>
                    <div className="border-t border-border-subtle/60 px-4 py-3 text-xs leading-relaxed text-text-muted">
                      {typeof category.content === "function" ? (
                        <category.content />
                      ) : (
                        category.content
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
