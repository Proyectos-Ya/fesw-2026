"use client";

import { useEffect, useRef } from "react";
import { driver, type DriveStep, type Driver } from "driver.js";
import "driver.js/dist/driver.css";
import {
  useOnboardingStore,
} from "../store/useOnboardingStore";
import type { TourName } from "../services/onboardingService";

export function openMobileSidebarIfNeeded() {
  const mobileBtn = document.querySelector<HTMLElement>(
    '[data-tour="mobile-menu-toggle"]',
  );
  const searchItem = document.querySelector<HTMLElement>(
    '[data-tour="sidebar-search"]',
  );

  // Si estamos en móvil y el ítem de búsqueda no es visible, abrimos el menú
  if (
    mobileBtn &&
    mobileBtn.offsetParent !== null &&
    (!searchItem ||
      searchItem.offsetParent === null ||
      searchItem.getBoundingClientRect().right <= 0 ||
      mobileBtn.getAttribute("aria-expanded") === "false")
  ) {
    mobileBtn.click();
  }
}

export const HOME_STEPS: DriveStep[] = [
  {
    element: '[data-tour="home-recommendations"]',
    popover: {
      title: "Compatibilidad y Matches Automáticos",
      description:
        "Aquí verás cada día las licitaciones con mayor porcentaje de compatibilidad según el perfil de tu empresa.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: '[data-tour="sidebar-search"]',
    popover: {
      title: "Buscador Manual de Licitaciones",
      description:
        "¿Buscas una compra pública específica? Usa el explorador manual para filtrar por palabras clave, región o presupuesto.",
      side: "right",
      align: "center",
    },
    onHighlightStarted: () => {
      openMobileSidebarIfNeeded();
    },
  },
  {
    element: '[data-tour="sidebar-matches"]',
    popover: {
      title: "Todos tus Matches",
      description:
        "Revisa el listado completo de oportunidades compatibles. Aquí puedes descartar las que no te interesen o guardarlas para analizarlas a fondo.",
      side: "right",
      align: "center",
    },
  },
  {
    element: '[data-tour="sidebar-seguimiento"]',
    popover: {
      title: "Tu Embudo de Ventas",
      description:
        "En 'Guardados' y 'Tablero' podrás organizar tus licitaciones favoritas en un tablero Kanban, moviéndolas desde el análisis inicial hasta la postulación.",
      side: "right",
      align: "center",
    },
  },
  {
    element: '[data-tour="sidebar-administracion"]',
    popover: {
      title: "Gestión de tu Empresa",
      description:
        "Configura las palabras clave de tu negocio en 'Mi empresa' y ajusta tus 'Alertas' para que Chiripa te notifique antes de que venza un plazo.",
      side: "right",
      align: "center",
    },
  },
  {
    element: '[data-tour="help-center-trigger"]',
    popover: {
      title: "Ayuda siempre a mano",
      description:
        "Si alguna vez te pierdes o quieres repetir este recorrido, abre el Centro de Ayuda. ¡Estás listo para empezar a ganar licitaciones!",
      side: "right",
      align: "center",
    },
  },
];

export const DETAIL_STEPS: DriveStep[] = [
  {
    element: '[data-tour="detail-header"]',
    popover: {
      title: "Información General",
      description:
        "Revisa el código, título, organismo comprador, plazos de cierre y el porcentaje de compatibilidad con tu empresa.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: '[data-tour="detail-actions"]',
    popover: {
      title: "Gestión y Exportación",
      description:
        "Agrega la licitación a tu tablero Kanban, guárdala en favoritos o descarga resúmenes ejecutivos en PDF y Excel.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: '[data-tour="detail-ai-panel"]',
    popover: {
      title: "Asistencia e IA",
      description:
        "Genera propuestas técnicas automáticas con el Asistente o solicita un análisis detallado de riesgos y requisitos de las bases.",
      side: "left",
      align: "start",
    },
  },
  {
    element: '[data-tour="detail-bases"]',
    popover: {
      title: "Bases y Requisitos",
      description:
        "Visualiza y busca dentro de los documentos oficiales y cláusulas administrativas y técnicas de la licitación.",
      side: "top",
      align: "start",
    },
  },
  {
    element: '[data-tour="detail-anexos"]',
    popover: {
      title: "Anexos y Documentos",
      description:
        "Descarga formularios oficiales, formatos de declaración jurada y plantillas requeridas para postular.",
      side: "top",
      align: "start",
    },
  },
  {
    element: '[data-tour="detail-calendario"]',
    popover: {
      title: "Calendario de Hitos",
      description:
        "Controla las fechas límite de preguntas, respuestas, cierre de postulaciones y adjudicación estimada.",
      side: "top",
      align: "start",
    },
  },
];

export const DRAFT_STEPS: DriveStep[] = [
  {
    element: '[data-tour="draft-factibilidad"]',
    popover: {
      title: "Factibilidad y Exigencias",
      description:
        "Aquí se escanean las bases y anexos para estructurar tu propuesta. Si la IA detecta que falta información excluyente en tu perfil, te hará preguntas clave antes de continuar.",
      side: "bottom",
      align: "start",
    },
  },
  {
    element: '[data-tour="draft-borrador-container"]',
    popover: {
      title: "Borrador de Oferta",
      description:
        "Una vez analizado, aquí verás los próximos pasos a seguir, los textos listos para copiar y pegar en Mercado Público, y opciones para generar documentos técnicos.",
      side: "top",
      align: "start",
    },
  },
  {
    element: '[data-tour="draft-cotizacion"]',
    popover: {
      title: "Cotización Financiera",
      description:
        "Calcula los costos de tu oferta. El sistema autocompleta los campos según las bases, pero puedes añadir ítems manualmente, guardar tu progreso y exportarlo a CSV o PDF.",
      side: "top",
      align: "start",
    },
  },
];

export function getStepsForTour(tourName: TourName | null): DriveStep[] | null {
  switch (tourName) {
    case "home":
      return HOME_STEPS;
    case "detail":
      return DETAIL_STEPS;
    case "draft":
      return DRAFT_STEPS;
    default:
      return null;
  }
}

export function switchDetailTabIfNeeded(
  tourName: TourName | null,
  stepIndex?: number,
) {
  if (tourName !== "detail" || typeof stepIndex !== "number") return;
  if (stepIndex === 3) {
    document.querySelector<HTMLElement>('[data-tab-target="bases"]')?.click();
  } else if (stepIndex === 4) {
    document.querySelector<HTMLElement>('[data-tab-target="anexos"]')?.click();
  } else if (stepIndex === 5) {
    document.querySelector<HTMLElement>('[data-tab-target="calendario"]')?.click();
  }
}

export function switchDraftTabIfNeeded(
  tourName: TourName | null,
  stepIndex?: number,
) {
  if (tourName !== "draft" || typeof stepIndex !== "number") return;
  if (stepIndex === 0) {
    document
      .querySelector<HTMLElement>(
        '[data-tab-target="factibilidad"], [data-tab-target="analisis"]',
      )
      ?.click();
  } else if (stepIndex === 1) {
    document.querySelector<HTMLElement>('[data-tab-target="borrador"]')?.click();
  } else if (stepIndex === 2) {
    document.querySelector<HTMLElement>('[data-tab-target="cotizacion"]')?.click();
    setTimeout(() => {
      const toggleBtn = document.querySelector<HTMLElement>(
        '[data-action="toggle-quotation"]',
      );
      if (toggleBtn && toggleBtn.getAttribute("aria-expanded") !== "true") {
        toggleBtn.click();
      }
    }, 100);
  }
}

export function GuidedTour() {
  const activeTour = useOnboardingStore((state) => state.activeTour);
  const currentTourStep = useOnboardingStore((state) => state.currentTourStep);
  const setTourStep = useOnboardingStore((state) => state.setTourStep);
  const skipTour = useOnboardingStore((state) => state.skipTour);
  const markOnboardingAsCompletedAsync = useOnboardingStore(
    (state) => state.markOnboardingAsCompletedAsync,
  );

  const driverRef = useRef<Driver | null>(null);

  const steps = getStepsForTour(activeTour);

  useEffect(() => {
    if (!activeTour || !steps || steps.length === 0) {
      if (driverRef.current?.isActive()) {
        driverRef.current.destroy();
      }
      driverRef.current = null;
      return;
    }

    const currentTourName = activeTour;
    const startIndex = useOnboardingStore.getState().currentTourStep;

    const driverObj = driver({
      showProgress: true,
      animate: true,
      allowClose: false,
      overlayColor: "rgba(27, 24, 20, 0.65)",
      stagePadding: 8,
      stageRadius: 10,
      waitForElement: 2500,
      progressText: "Paso {{current}} de {{total}}",
      nextBtnText: "Siguiente",
      prevBtnText: "Anterior",
      doneBtnText: "Finalizar",
      closeBtnLabel: "Omitir tour",
      showButtons: ["next", "previous", "close"],
      popoverClass:
        "chiripa-tour-popover bg-surface-card text-text-strong font-sans border border-border-subtle shadow-xl rounded-lg dark:bg-gray-900 dark:text-white dark:border-gray-700",
      steps,
      onNextClick: (_element, _step, opts) => {
        const currentIdx = opts.state.activeIndex ?? 0;
        const nextIdx = currentIdx + 1;
        if (nextIdx >= steps.length) {
          opts.driver.destroy();
          void markOnboardingAsCompletedAsync(currentTourName);
        } else {
          setTourStep(nextIdx);
          switchDetailTabIfNeeded(currentTourName, nextIdx);
          switchDraftTabIfNeeded(currentTourName, nextIdx);
          opts.driver.moveTo(nextIdx);
        }
      },
      onPrevClick: (_element, _step, opts) => {
        const currentIdx = opts.state.activeIndex ?? 0;
        const prevIdx = Math.max(0, currentIdx - 1);
        setTourStep(prevIdx);
        switchDetailTabIfNeeded(currentTourName, prevIdx);
        switchDraftTabIfNeeded(currentTourName, prevIdx);
        opts.driver.moveTo(prevIdx);
      },
      onCloseClick: (_element, _step, opts) => {
        opts.driver.destroy();
        void markOnboardingAsCompletedAsync(currentTourName);
      },
      onHighlightStarted: (_element, _step, opts) => {
        if (typeof opts.index === "number") {
          setTourStep(opts.index);
          switchDetailTabIfNeeded(currentTourName, opts.index);
          switchDraftTabIfNeeded(currentTourName, opts.index);
        }
      },
      onPopoverRender: (popover, opts) => {
        if (popover.footerButtons.querySelector('[data-tour-action="skip"]')) {
          return;
        }
        const skipButton = document.createElement("button");
        skipButton.type = "button";
        skipButton.textContent = "Omitir tour";
        skipButton.setAttribute("data-tour-action", "skip");
        skipButton.className = "driver-popover-skip-btn";
        skipButton.addEventListener("click", () => {
          opts.driver.destroy();
          void markOnboardingAsCompletedAsync(currentTourName);
        });
        popover.footerButtons.prepend(skipButton);
      },
      onDestroyed: (_element, _step, opts) => {
        if (opts.reason === "done") {
          void markOnboardingAsCompletedAsync(currentTourName);
        } else {
          skipTour(currentTourName);
        }
      },
    });

    driverRef.current = driverObj;
    driverObj.drive(startIndex);

    return () => {
      if (driverRef.current?.isActive()) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
    };
  }, [activeTour, steps, markOnboardingAsCompletedAsync, setTourStep, skipTour]);

  void currentTourStep;

  return null;
}
