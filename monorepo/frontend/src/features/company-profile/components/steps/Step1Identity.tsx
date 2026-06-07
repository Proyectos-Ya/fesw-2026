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
        <h2 className="mb-1 text-xl font-bold text-brand-primary-900">
          Identidad de tu empresa
        </h2>
        <p className="text-sm text-zinc-600">
          Ingresa los datos de la empresa que va a postular a licitaciones.
        </p>
      </div>

      <div className="mb-6 rounded-input border border-brand-primary-100 bg-brand-primary-50 px-4 py-3 text-sm text-zinc-600">
        Registrado como administrador:{" "}
        <span className="font-semibold text-brand-primary-900">{adminName}</span>
      </div>

      <div className="flex flex-col gap-5">
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
