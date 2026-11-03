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

const NAVIGATION_SUBSECTIONS = [
  {
    iconName: "sparkles",
    title: "Inicio",
    text: "Resumen diario con tus mejores recomendaciones generadas por IA, donde destacan las oportunidades urgentes o de altísima compatibilidad.",
  },
  {
    iconName: "search",
    title: "Buscar",
    text: "Explorador manual de Mercado Público. Úsalo cuando necesites cazar licitaciones específicas usando filtros estrictos (región, estado, presupuesto).",
  },
  {
    iconName: "target",
    title: "Matches",
    text: "Catálogo completo de licitaciones afines a tu rubro. Es tu bandeja de entrada principal para revisar, descartar o guardar oportunidades.",
  },
  {
    iconName: "bookmark",
    title: "Guardados",
    text: "Tu buzón de licitaciones pre-seleccionadas. Todo lo que marques con la etiqueta de guardado llegará aquí para esperar tu revisión detallada.",
  },
  {
    iconName: "kanban",
    title: "Tablero (Kanban)",
    text: "Espacio de trabajo visual. Organiza tu proceso de postulación moviendo tarjetas por columnas (Análisis, Borrador, Revisión y Enviado) para coordinar con tu equipo.",
  },
];

const PROFILE_SUBSECTIONS = [
  {
    iconName: "info",
    title: "Información",
    text: "Contiene los datos vitales de tu empresa (descripción, años de experiencia, número de empleados, regiones operativas, rubros y certificaciones). Mantener esto completo y actualizado mejora directamente la calidad y precisión de los matches.",
  },
  {
    iconName: "tag",
    title: "Palabras Claves",
    text: "Son elementos fundamentales para la calidad del match. La aplicación añade nuevas palabras clave mediante tu interacción con ella para afinar los resultados. También puedes agregar o eliminar términos manualmente editando esta sección.",
  },
  {
    iconName: "users",
    title: "Equipo",
    text: "Pestaña para gestionar a los miembros de tu espacio de trabajo. Controla quiénes tienen acceso y sus niveles de permiso sobre el perfil de la empresa, los matches y el seguimiento de licitaciones.",
  },
];

const DETAIL_SUBSECTIONS = [
  {
    iconName: "layout-template",
    title: "Información de Licitación",
    text: "Explora el encabezado para conocer el organismo convocante, montos estimados, fechas límite y el nivel de compatibilidad semántica con tu perfil.",
  },
  {
    iconName: "file-text",
    title: "Bases",
    text: "Consulta los requisitos técnicos, criterios de evaluación y condiciones administrativas para asegurar que tu oferta cumpla al 100%.",
  },
  {
    iconName: "paperclip",
    title: "Anexos",
    text: "Accede y descarga todos los documentos adjuntos, formatos editables y declaraciones juradas necesarias para preparar tu postulación.",
  },
  {
    iconName: "calendar",
    title: "Calendario",
    text: "Sigue el cronograma oficial del proceso: etapas de consultas, respuestas, apertura de ofertas y fecha estimada de adjudicación.",
  },
  {
    iconName: "file-signature",
    title: "Generar Postulación",
    text: "Utiliza la IA para estructurar borradores iniciales de tu propuesta técnica y comercial basados en las bases de la licitación.",
  },
  {
    iconName: "bot",
    title: "Análisis y Asistencia IA",
    text: "Haz preguntas directas al Asistente sobre puntos específicos de la licitación o solicita resúmenes de riesgos y requerimientos clave.",
  },
];

export const HELP_CATEGORIES: ReadonlyArray<HelpCategory> = [
  {
    id: "navigation",
    title: "Navegación por Chiripa",
    icon: Map,
    matchRoutes: ["/", "/buscar", "/guardados", "/tablero", "/alertas"],
    content: (
      <div className="space-y-2 pt-1">
        {NAVIGATION_SUBSECTIONS.map((sub) => (
          <details
            key={sub.title}
            className="group/sub rounded-md border border-border-subtle/80 bg-surface-card p-2.5 transition-colors hover:border-border-default"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between font-medium text-text-strong select-none hover:text-primary transition-colors [&::-webkit-details-marker]:hidden">
              <span className="flex items-center gap-2">
                <Icon
                  name={sub.iconName}
                  size={16}
                  className="w-4 h-4 text-text-muted transition-colors"
                />
                <span className="font-semibold text-sm">{sub.title}</span>
              </span>
              <ChevronDown
                size={14}
                className="text-text-subtle transition-transform duration-200 group-open/sub:rotate-180"
              />
            </summary>
            <p className="mt-2 text-[0.8rem] text-text-muted leading-relaxed pl-6">
              {sub.text}
            </p>
          </details>
        ))}
      </div>
    ),
  },
  {
    id: "profile",
    title: "Mi perfil de empresa",
    icon: Building2,
    matchRoutes: ["/empresa", "/perfil", "/workspaces", "/configuracion"],
    content: (
      <div className="space-y-2 pt-1">
        {PROFILE_SUBSECTIONS.map((sub) => (
          <details
            key={sub.title}
            className="group/sub rounded-md border border-border-subtle/80 bg-surface-card p-2.5 transition-colors hover:border-border-default"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between font-medium text-text-strong select-none hover:text-primary transition-colors [&::-webkit-details-marker]:hidden">
              <span className="flex items-center gap-2">
                <Icon
                  name={sub.iconName}
                  size={16}
                  className="w-4 h-4 text-text-muted transition-colors"
                />
                <span className="font-semibold text-sm">{sub.title}</span>
              </span>
              <ChevronDown
                size={14}
                className="text-text-subtle transition-transform duration-200 group-open/sub:rotate-180"
              />
            </summary>
            <p className="mt-2 text-[0.8rem] text-text-muted leading-relaxed pl-6">
              {sub.text}
            </p>
          </details>
        ))}
      </div>
    ),
  },
  {
    id: "detail",
    title: "Vista detallada de licitaciones",
    icon: Search,
    matchRoutes: ["/matches"],
    content: (
      <div className="space-y-2 pt-1">
        {DETAIL_SUBSECTIONS.map((sub) => (
          <details
            key={sub.title}
            className="group/sub rounded-md border border-border-subtle/80 bg-surface-card p-2.5 transition-colors hover:border-border-default"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between font-medium text-text-strong select-none hover:text-primary transition-colors [&::-webkit-details-marker]:hidden">
              <span className="flex items-center gap-2">
                <Icon
                  name={sub.iconName}
                  size={16}
                  className="w-4 h-4 text-text-muted transition-colors"
                />
                <span className="font-semibold text-sm">{sub.title}</span>
              </span>
              <ChevronDown
                size={14}
                className="text-text-subtle transition-transform duration-200 group-open/sub:rotate-180"
              />
            </summary>
            <p className="mt-2 text-[0.8rem] text-text-muted leading-relaxed pl-6">
              {sub.text}
            </p>
          </details>
        ))}
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
        </div>
      </aside>
    </div>
  );
}
