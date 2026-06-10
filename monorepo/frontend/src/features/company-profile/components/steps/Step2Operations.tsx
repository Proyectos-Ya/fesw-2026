"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { step2Schema, type Step2Data } from "../../profileSchema";
import { Input } from "@/features/shared/components/Input";
import { ChipSelect } from "@/features/shared/components/ChipSelect";
import { WizardNavigation } from "../WizardNavigation";
import { REGIONS } from "../../data/regions";

interface Step2Props {
  defaultValues: Partial<Step2Data>;
  onNext: (data: Step2Data) => void;
  onBack: () => void;
}

export function Step2Operations({ defaultValues, onNext, onBack }: Step2Props) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<Step2Data>({
    resolver: zodResolver(step2Schema),
    defaultValues: {
      regions: [],
      ...defaultValues,
    },
  });

  return (
    <div>
      <div className="mb-6">
        <h2 className="mb-1 text-2xl font-bold tracking-tight text-text-strong">Operación</h2>
        <p className="text-sm text-text-muted">
          ¿Dónde opera tu empresa y cuál es su tamaño?
        </p>
      </div>

      <div className="flex flex-col gap-8">
        <Controller
          name="regions"
          control={control}
          render={({ field }) => (
            <ChipSelect
              label="Regiones donde opera"
              options={REGIONS}
              selected={field.value}
              onChange={field.onChange}
              error={errors.regions?.message}
              hint="Selecciona todas las regiones donde puedes ejecutar proyectos."
            />
          )}
        />

        <div className="grid grid-cols-2 gap-6">
          <Input
            label="Años de experiencia"
            type="number"
            placeholder="Ej: 5"
            min={0}
            error={errors.years_experience?.message}
            {...register("years_experience", { valueAsNumber: true })}
          />
          <Input
            label="Número de empleados"
            type="number"
            placeholder="Ej: 12"
            min={1}
            error={errors.num_employees?.message}
            {...register("num_employees", { valueAsNumber: true })}
          />
        </div>
      </div>

      <WizardNavigation
        onBack={onBack}
        onNext={handleSubmit(onNext)}
        isFirstStep={false}
        isLastStep={false}
      />
    </div>
  );
}
