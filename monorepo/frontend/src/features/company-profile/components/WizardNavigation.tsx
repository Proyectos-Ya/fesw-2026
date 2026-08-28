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
  const label = nextLabel ?? (isLastStep ? "Guardar perfil y comenzar" : "Siguiente");
  return (
    <div className="mt-10 flex items-center justify-between border-t border-border-subtle pt-8">
      <Button
        type="button"
        variant="ghost"
        onClick={onBack}
        disabled={isFirstStep}
        className={isFirstStep ? "invisible" : "px-0 hover:bg-transparent hover:text-primary font-bold"}
      >
        ← Volver
      </Button>
      <Button 
        type="button" 
        variant={isLastStep ? "accent" : "primary"} 
        onClick={onNext} 
        isLoading={isLoading}
        className="px-8 font-bold"
      >
        {label} {!isLastStep && "→"}
      </Button>
    </div>
  );
}
