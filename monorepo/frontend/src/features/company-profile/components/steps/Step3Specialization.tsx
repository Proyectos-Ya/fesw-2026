"use client";

import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { step3Schema, type Step3Data } from "../../profileSchema";
import { Textarea } from "@/features/shared/components/Textarea";
import { ChipSelect } from "@/features/shared/components/ChipSelect";
import { TagInput } from "@/features/shared/components/TagInput";
import { WizardNavigation } from "../WizardNavigation";
import { SECTORS } from "../../data/sectors";

interface Step3Props {
  defaultValues: Partial<Step3Data>;
  onNext: (data: Step3Data) => void;
  onBack: () => void;
}

export function Step3Specialization({ defaultValues, onNext, onBack }: Step3Props) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<Step3Data>({
    resolver: zodResolver(step3Schema),
    defaultValues: {
      sectors: [],
      keywords: [],
      certifications: [],
      description: "",
      ...defaultValues,
    },
  });

  const description = watch("description");

  return (
    <div>
      <div className="mb-6">
        <h2 className="mb-1 text-2xl font-bold tracking-tight text-text-strong">Especialización</h2>
        <p className="text-sm text-text-muted">
          Esta información es la base del motor de matching. Mientras más detallada, mejores
          serán las recomendaciones.
        </p>
      </div>

      <div className="flex flex-col gap-8">
        <Controller
          name="sectors"
          control={control}
          render={({ field }) => (
            <ChipSelect
              label="Rubros principales"
              options={SECTORS}
              selected={field.value}
              onChange={field.onChange}
              error={errors.sectors?.message}
            />
          )}
        />

        <Controller
          name="keywords"
          control={control}
          render={({ field }) => (
            <TagInput
              label="Palabras clave de experiencia"
              tags={field.value}
              onChange={field.onChange}
              placeholder="Ej: luminarias LED, pavimentación, redes húmedas..."
              hint="Presiona Enter o coma para añadir. Mejoran la precisión del match."
              error={errors.keywords?.message}
            />
          )}
        />

        <Controller
          name="certifications"
          control={control}
          render={({ field }) => (
            <TagInput
              label="Certificaciones relevantes"
              tags={field.value}
              onChange={field.onChange}
              placeholder="Ej: ISO 9001, OHSAS 18001, SEC..."
              hint="Presiona Enter o coma para añadir."
              error={errors.certifications?.message}
              optional
            />
          )}
        />

        <Textarea
          label="Descripción de la empresa"
          placeholder="Ej: Constructora especializada en obras civiles menores y mantención de infraestructura municipal..."
          hint="Describe qué hace tu empresa y en qué se especializa."
          charCount={description?.length ?? 0}
          maxChars={1000}
          error={errors.description?.message}
          {...register("description")}
        />
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
