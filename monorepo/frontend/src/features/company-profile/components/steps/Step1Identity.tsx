"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { formatRut, step1Schema, type Step1Data } from "../../profileSchema";
import { checkRutExists, type CompanyProfileImport } from "../../services/supplierService";
import { Input } from "@/features/shared/components/Input";
import { WizardNavigation } from "../WizardNavigation";
import { CompanyImportCard } from "../CompanyImportCard";
import { ImportedFieldReview, isFieldLocked, type FieldReview } from "../ImportedFieldReview";

interface Step1Props {
  defaultValues: Partial<Step1Data>;
  adminName: string;
  importedProfile: CompanyProfileImport | null;
  onImported: (profile: CompanyProfileImport) => void;
  legalNameReview: FieldReview;
  /** "Siguiente" queda bloqueado mientras la razón social importada no se confirma. */
  nextBlocked: boolean;
  onNext: (data: Step1Data) => void;
  onBack: () => void;
}

export function Step1Identity({
  defaultValues,
  adminName,
  importedProfile,
  onImported,
  legalNameReview,
  nextBlocked,
  onNext,
  onBack,
}: Step1Props) {
  const {
    register,
    handleSubmit,
    setError,
    watch,
    setValue,
    formState: { errors },
  } = useForm<Step1Data>({
    resolver: zodResolver(step1Schema),
    defaultValues: {
      ...defaultValues,
      rut: defaultValues.rut ? formatRut(defaultValues.rut) : defaultValues.rut,
    },
    mode: "onTouched",
  });
  const [isCheckingRut, setIsCheckingRut] = useState(false);
  const rutField = register("rut");
  const rut = watch("rut");

  const setLegalName = (value: string) =>
    setValue("legal_name", value, { shouldDirty: true, shouldValidate: value !== "" });

  const handleImported = (profile: CompanyProfileImport) => {
    onImported(profile);
    const legalName = profile.legal_name.trim();
    const isOtherRut =
      importedProfile !== null && formatRut(importedProfile.rut) !== formatRut(profile.rut);
    // Con otro RUT el wizard vacía la razón social anterior; el campo vivo hace lo mismo.
    if (legalName) setLegalName(legalName);
    else if (isOtherRut) setLegalName("");
  };

  const handleClearLegalName = () => {
    legalNameReview.onClear();
    setLegalName("");
  };

  const handleNext = async (data: Step1Data) => {
    setIsCheckingRut(true);
    try {
      if (await checkRutExists(data.rut)) {
        setError("rut", {
          type: "manual",
          message: "Este RUT ya está registrado en la plataforma.",
        });
        return;
      }
    } catch {
      // Si la verificación falla (red, servidor), no se bloquea el avance:
      // el backend vuelve a validar el duplicado al crear la empresa.
    } finally {
      setIsCheckingRut(false);
    }
    onNext(data);
  };

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
        <div className="flex flex-col gap-2">
          <Input
            label="Nombre de la empresa"
            placeholder="Ej: Constructora Pérez y Asociados Ltda."
            error={errors.legal_name?.message}
            readOnly={isFieldLocked(legalNameReview.status)}
            {...register("legal_name")}
          />
          <ImportedFieldReview
            fieldLabel="razón social"
            {...legalNameReview}
            onClear={handleClearLegalName}
          />
        </div>
        <Input
          label="Nombre de fantasía (opcional)"
          placeholder="Ej: Constructora Pérez"
          hint="El nombre con el que se conoce comercialmente a tu empresa."
          error={errors.trade_name?.message}
          {...register("trade_name")}
        />
        <Input
          label="RUT de la empresa"
          placeholder="Ej: 76.123.456-7"
          hint="Formato: XX.XXX.XXX-X"
          error={errors.rut?.message}
          maxLength={12}
          {...rutField}
          onChange={(e) => {
            e.target.value = formatRut(e.target.value);
            return rutField.onChange(e);
          }}
        />
        <CompanyImportCard
          rut={rut ?? ""}
          imported={importedProfile}
          onImported={handleImported}
          onInvalidRut={(message) => setError("rut", { type: "manual", message })}
        />
      </div>

      <WizardNavigation
        onBack={onBack}
        onNext={handleSubmit(handleNext)}
        isFirstStep
        isLastStep={false}
        isLoading={isCheckingRut}
        nextDisabled={nextBlocked}
      />
    </div>
  );
}
