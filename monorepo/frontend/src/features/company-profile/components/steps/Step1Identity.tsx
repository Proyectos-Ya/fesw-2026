"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { step1Schema, type Step1Data } from "../../profileSchema";
import { Input } from "@/features/shared/components/Input";
import { WizardNavigation } from "../WizardNavigation";

interface Step1Props {
  defaultValues: Partial<Step1Data>;
  adminName: string;
  onNext: (data: Step1Data) => void;
  onBack: () => void;
}

export function Step1Identity({ defaultValues, adminName, onNext, onBack }: Step1Props) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Step1Data>({
    resolver: zodResolver(step1Schema),
    defaultValues,
  });

  return (
    <div>
      <div className="mb-6">
        <h2 className="mb-1 text-2xl font-bold tracking-tight text-text-strong">
          Identidad de tu empresa
        </h2>
        <p className="text-sm text-text-muted">
          Ingresa los datos de la empresa que va a postular a licitaciones.
        </p>
      </div>

      <div className="mb-8 rounded-md border border-primary-border bg-primary-soft/50 px-4 py-3.5 text-sm text-text-body flex items-center gap-3 shadow-sm">
        <div className="size-2 rounded-full bg-primary animate-pulse" />
        <span>
          Registrado como administrador:{" "}
          <span className="font-bold text-primary">{adminName}</span>
        </span>
      </div>

      <div className="flex flex-col gap-6">
        <Input
          label="Nombre de la empresa"
          placeholder="Ej: Constructora Pérez y Asociados Ltda."
          error={errors.legal_name?.message}
          {...register("legal_name")}
        />
        <Input
          label="RUT de la empresa"
          placeholder="Ej: 76.123.456-7"
          hint="Formato: XX.XXX.XXX-X"
          error={errors.rut?.message}
          {...register("rut")}
        />
      </div>

      <WizardNavigation
        onBack={onBack}
        onNext={handleSubmit(onNext)}
        isFirstStep
        isLastStep={false}
      />
    </div>
  );
}
