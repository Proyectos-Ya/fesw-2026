interface WizardProgressProps {
  currentStep: number;
  totalSteps: number;
}

export function WizardProgress({ currentStep, totalSteps }: WizardProgressProps) {
  const percentage = Math.round((currentStep / totalSteps) * 100);
  return (
    <div className="mb-8 flex flex-col gap-2">
      <div className="flex items-center justify-between text-sm font-medium">
        <span className="text-zinc-600">
          Paso {currentStep} de {totalSteps}
        </span>
        <span className="text-brand-primary-700">{percentage}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-200">
        <div
          className="h-full rounded-full bg-brand-primary-600 transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
