"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { driver, type DriveStep, type Driver } from "driver.js";
import "driver.js/dist/driver.css";
import { useCompany } from "@/features/company-profile/components/CompanyProvider";
import { useWorkspace } from "@/features/workspaces/WorkspaceContext";
import { useOnboardingStore } from "../store/useOnboardingStore";

export interface TourStep extends DriveStep {
  route: string;
}

export const GUIDED_TOUR_STEPS: TourStep[] = [
  {
    route: "/",
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
    route: "/buscar",
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
    route: "/buscar",
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
  const router = useRouter();
  const pathname = usePathname();

  const { company } = useCompany();
  const { activeWorkspace } = useWorkspace();

  const isTourActive = useOnboardingStore((state) => state.isTourActive);
  const currentTourStep = useOnboardingStore((state) => state.currentTourStep);
  const setTourStep = useOnboardingStore((state) => state.setTourStep);
  const markOnboardingAsCompletedAsync = useOnboardingStore(
    (state) => state.markOnboardingAsCompletedAsync,
  );

  const driverRef = useRef<Driver | null>(null);
  const isNavigatingRef = useRef(false);

  const hasActiveCompanyContext =
    company.status === "with-company" || activeWorkspace !== null;

  const handleNext = (activeIdx: number, driverObj: Driver) => {
    const nextIdx = activeIdx + 1;
    if (nextIdx >= GUIDED_TOUR_STEPS.length) {
      isNavigatingRef.current = false;
      driverObj.destroy();
      void markOnboardingAsCompletedAsync();
      return;
    }

    const nextStep = GUIDED_TOUR_STEPS[nextIdx];
    if (nextStep && nextStep.route !== pathname) {
      isNavigatingRef.current = true;
      driverObj.destroy();
      setTourStep(nextIdx);
      router.push(nextStep.route);
    } else {
      setTourStep(nextIdx);
      driverObj.moveTo(nextIdx);
    }
  };

  const handlePrev = (activeIdx: number, driverObj: Driver) => {
    const prevIdx = activeIdx - 1;
    if (prevIdx < 0) return;

    const prevStep = GUIDED_TOUR_STEPS[prevIdx];
    if (prevStep && prevStep.route !== pathname) {
      isNavigatingRef.current = true;
      driverObj.destroy();
      setTourStep(prevIdx);
      router.push(prevStep.route);
    } else {
      setTourStep(prevIdx);
      driverObj.moveTo(prevIdx);
    }
  };

  useEffect(() => {
    if (!isTourActive || !hasActiveCompanyContext) {
      if (driverRef.current?.isActive()) {
        driverRef.current.destroy();
      }
      driverRef.current = null;
      isNavigatingRef.current = false;
      return;
    }

    const targetStepIndex = useOnboardingStore.getState().currentTourStep;
    const targetStep = GUIDED_TOUR_STEPS[targetStepIndex] ?? GUIDED_TOUR_STEPS[0];

    // Si no estamos en la ruta esperada para este paso, navegamos
    if (targetStep && targetStep.route !== pathname) {
      isNavigatingRef.current = true;
      router.push(targetStep.route);
      return;
    }

    isNavigatingRef.current = false;

    if (driverRef.current?.isActive()) {
      driverRef.current.destroy();
    }

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
      steps: GUIDED_TOUR_STEPS,
      onNextClick: (_element, _step, opts) => {
        const currentIdx = opts.state.activeIndex ?? targetStepIndex;
        handleNext(currentIdx, opts.driver);
      },
      onPrevClick: (_element, _step, opts) => {
        const currentIdx = opts.state.activeIndex ?? targetStepIndex;
        handlePrev(currentIdx, opts.driver);
      },
      onCloseClick: (_element, _step, opts) => {
        isNavigatingRef.current = false;
        opts.driver.destroy();
        void markOnboardingAsCompletedAsync();
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
          isNavigatingRef.current = false;
          void markOnboardingAsCompletedAsync();
          opts.driver.destroy();
        });
        popover.footerButtons.prepend(skipButton);
      },
      onDestroyed: () => {
        if (isNavigatingRef.current) {
          // Transición de ruta en curso: NO completar onboarding
          return;
        }
        void markOnboardingAsCompletedAsync();
      },
    });

    driverRef.current = driverObj;
    driverObj.drive(targetStepIndex);

    return () => {
      if (driverRef.current?.isActive() && !isNavigatingRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTourActive, hasActiveCompanyContext, pathname]);

  void currentTourStep;

  return null;
}
