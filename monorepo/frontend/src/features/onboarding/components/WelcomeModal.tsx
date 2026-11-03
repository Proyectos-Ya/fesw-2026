"use client";

import { useCompany } from "@/features/company-profile/components/CompanyProvider";
import { useWorkspace } from "@/features/workspaces/WorkspaceContext";
import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Icon } from "@/features/shared/components/Icon";
import { useOnboardingStore } from "../store/useOnboardingStore";

export function WelcomeModal() {
  const { company } = useCompany();
  const { activeWorkspace } = useWorkspace();

  const hasHydrated = useOnboardingStore((state) => state._hasHydrated);
  const hasCompletedOnboarding = useOnboardingStore(
    (state) => state.hasCompletedOnboarding,
  );
  const isTourActive = useOnboardingStore((state) => state.isTourActive);
  const startTour = useOnboardingStore((state) => state.startTour);
  const markOnboardingAsCompletedAsync = useOnboardingStore(
    (state) => state.markOnboardingAsCompletedAsync,
  );

  const hasActiveCompanyContext =
    company.status === "with-company" || activeWorkspace !== null;

  const isOpen =
    hasHydrated &&
    !hasCompletedOnboarding &&
    !isTourActive &&
    hasActiveCompanyContext;

  if (!isOpen) return null;

  const handleSkip = () => {
    void markOnboardingAsCompletedAsync();
  };

  return (
    <Dialog
      open={isOpen}
      title="¡Bienvenido a Chiripa!"
      onClose={() => {}}
      preventOutsideClose={true}
    >
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-lg bg-primary-soft p-3 text-primary">
          <Icon name="sparkles" size={20} className="mt-0.5 flex-none" />
          <p className="text-xs font-medium text-text-body leading-relaxed">
            Tu perfil de empresa ya está listo. Te invitamos a conocer en menos
            de un minuto el flujo principal para encontrar y analizar tus
            mejores licitaciones.
          </p>
        </div>

        <p className="text-sm text-text-muted leading-relaxed">
          Durante el recorrido veremos cómo interpretar tu porcentaje de
          compatibilidad, cómo usar el buscador manual y dónde revisar las
          exigencias clave con nuestro asistente de IA.
        </p>

        <div className="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={handleSkip}
          >
            Omitir por ahora
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={startTour}
          >
            Iniciar recorrido
            <Icon name="arrow-right" size={16} />
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
