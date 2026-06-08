import { Button } from "@/features/shared/components/Button";

interface WizardNavigationProps {
  onBack: () => void;
  onNext: () => void;
  isFirstStep: boolean;
  isLastStep: boolean;
  nextLabel?: string;
  isLoading?: boolean;
}

export function WizardNavigation({
  onBack,
  onNext,
  isFirstStep,
  isLastStep,
  nextLabel,
  isLoading = false,
}: WizardNavigationProps) {
  const label = nextLabel ?? (isLastStep ? "Guardar perfil y comenzar" : "Siguiente →");
  return (
    <div className="mt-8 flex items-center justify-between">
      <Button
        type="button"
        variant="ghost"
        onClick={onBack}
        disabled={isFirstStep}
        className={isFirstStep ? "invisible" : ""}
      >
        ← Atrás
      </Button>
      <Button type="button" variant="primary" onClick={onNext} isLoading={isLoading}>
        {label}
      </Button>
    </div>
  );
}
