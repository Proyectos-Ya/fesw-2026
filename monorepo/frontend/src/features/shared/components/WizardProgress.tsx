interface WizardProgressProps {
  currentStep: number;
  totalSteps: number;
}

export function WizardProgress({ currentStep, totalSteps }: WizardProgressProps) {
  const percentage = Math.round((currentStep / totalSteps) * 100);
  return (
    <div className="mb-8 flex flex-col gap-2.5">
      <div className="flex items-center justify-between text-xs font-semibold tracking-caps uppercase">
        <span className="text-text-muted">
          Paso {currentStep} de {totalSteps}
        </span>
        <span className="text-primary">{percentage}% completado</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-border-subtle/50">
        <div
          className="h-full rounded-full bg-primary shadow-teal transition-all duration-700 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
