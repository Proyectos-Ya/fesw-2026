"use client";

import { useEffect, useRef } from "react";
import { driver, type DriveStep, type Driver } from "driver.js";
import "driver.js/dist/driver.css";
import { useCompany } from "@/features/company-profile/components/CompanyProvider";
import { useWorkspace } from "@/features/workspaces/WorkspaceContext";
import { useOnboardingStore } from "../store/useOnboardingStore";

export const GUIDED_TOUR_STEPS: DriveStep[] = [
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

export function GuidedTour() {
  const { company } = useCompany();
  const { activeWorkspace } = useWorkspace();

  const isTourActive = useOnboardingStore((state) => state.isTourActive);
  const currentTourStep = useOnboardingStore((state) => state.currentTourStep);
  const setTourStep = useOnboardingStore((state) => state.setTourStep);
  const skipTour = useOnboardingStore((state) => state.skipTour);
  const completeOnboarding = useOnboardingStore(
    (state) => state.completeOnboarding,
  );

  const driverRef = useRef<Driver | null>(null);

  const hasActiveCompanyContext =
    company.status === "with-company" || activeWorkspace !== null;

  useEffect(() => {
    if (!isTourActive || !hasActiveCompanyContext) {
      if (driverRef.current?.isActive()) {
        driverRef.current.destroy();
      }
      driverRef.current = null;
      return;
    }

    const startIndex = useOnboardingStore.getState().currentTourStep;

    const driverObj = driver({
      showProgress: true,
      animate: true,
      allowClose: true,
      overlayColor: "rgba(27, 24, 20, 0.65)",
      stagePadding: 8,
      stageRadius: 10,
      progressText: "Paso {{current}} de {{total}}",
      nextBtnText: "Siguiente",
      prevBtnText: "Anterior",
      doneBtnText: "Finalizar",
      closeBtnLabel: "Omitir tour",
      showButtons: ["next", "previous", "close"],
      steps: GUIDED_TOUR_STEPS,
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
          skipTour();
          opts.driver.destroy();
        });
        popover.footerButtons.prepend(skipButton);
      },
      onDestroyed: (_element, _step, opts) => {
        if (opts.reason === "done") {
          completeOnboarding();
        } else {
          skipTour();
        }
      },
    });

    driverRef.current = driverObj;
    driverObj.drive(startIndex);

    return () => {
      if (driverObj.isActive()) {
        driverObj.destroy();
      }
      driverRef.current = null;
    };
    // Solo iniciamos/destruimos el motor cuando cambia la activación del tour o el Soft Gate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTourActive, hasActiveCompanyContext]);

  // Evita warning de variable no leída manteniendo suscripción si se requiere inspección
  void currentTourStep;

  return null;
}
