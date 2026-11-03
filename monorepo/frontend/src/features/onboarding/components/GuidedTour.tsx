"use client";

import { useEffect, useRef } from "react";
import { driver, type DriveStep, type Driver } from "driver.js";
import "driver.js/dist/driver.css";
import {
  useOnboardingStore,
} from "../store/useOnboardingStore";
import type { TourName } from "../services/onboardingService";

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
  },
  {
    element: '[data-tour="sidebar-help"]',
    popover: {
      title: "Centro de Ayuda y Guías Rápidas",
      description:
        "Encuentra explicaciones detalladas sobre el funcionamiento de la plataforma o reinicia los tours cuando lo necesites.",
      side: "right",
      align: "center",
    },
  },
];

export const DETAIL_STEPS: DriveStep[] = [
  {
    element: '[data-tour="match-detail-panel"]',
    popover: {
      title: "Exigencias y Asistente de IA",
      description:
        "Al abrir cualquier licitación podrás revisar el desglose de requisitos clave y consultar a nuestro asistente de IA sobre las bases.",
      side: "top",
      align: "start",
    },
  },
];

export const DRAFT_STEPS: DriveStep[] = [
  {
    element: '[data-tour="proposal-editor"]',
    popover: {
      title: "Editor de Propuesta y Borrador",
      description:
        "Redacta y estructura tu propuesta técnica y comercial con base en los requerimientos detectados.",
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
      allowClose: true,
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
          opts.driver.moveTo(nextIdx);
        }
      },
      onPrevClick: (_element, _step, opts) => {
        const currentIdx = opts.state.activeIndex ?? 0;
        const prevIdx = Math.max(0, currentIdx - 1);
        setTourStep(prevIdx);
        opts.driver.moveTo(prevIdx);
      },
      onCloseClick: (_element, _step, opts) => {
        opts.driver.destroy();
        void markOnboardingAsCompletedAsync(currentTourName);
      },
      onHighlightStarted: (_element, _step, opts) => {
        if (typeof opts.index === "number") {
          setTourStep(opts.index);
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
