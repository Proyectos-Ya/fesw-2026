"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import { useProfileWizard } from "../hooks/useProfileWizard";
import { WizardProgress } from "@/features/shared/components/WizardProgress";
import { Step1Identity } from "./steps/Step1Identity";
import { Step2Operations } from "./steps/Step2Operations";
import { Step3Specialization } from "./steps/Step3Specialization";
import { Step4Summary } from "./steps/Step4Summary";
import { z } from "zod";
import { profileSchema } from "../profileSchema";
import type { Step1Data, Step2Data, Step3Data } from "../profileSchema";
import { createSupplier, waitForMySupplier } from "../services/supplierService";
import { useCompany } from "./CompanyProvider";
import { SuccessView } from "./SuccessView";
import { ApiError, TimeoutError } from "@/features/shared/api/client";

/**
 * Respuestas tras las que la empresa pudo haber quedado creada de todas formas.
 *
 * - 409: la empresa puede ser del propio usuario, creada por un envío anterior
 *   que el navegador dio por perdido.
 * - 502, 503, 504: el proxy o el backend respondieron con error, pero el
 *   trabajo pudo terminar del otro lado.
 */
const MAY_HAVE_BEEN_CREATED_STATUSES = new Set([409, 502, 503, 504]);

function mayHaveBeenCreated(err: unknown): boolean {
  if (err instanceof ApiError) return MAY_HAVE_BEEN_CREATED_STATUSES.has(err.status);
  // Datos inválidos: la petición ni siquiera salió.
  if (err instanceof z.ZodError) return false;
  // Timeout o corte de red: no hubo respuesta, así que no se sabe qué pasó.
  return true;
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof z.ZodError) {
    return "Hay campos incompletos o inválidos. Revisa los pasos anteriores.";
  }
  if (err instanceof TimeoutError) return err.message;
  return "No se pudo guardar el perfil. Verifica tu conexión e inténtalo nuevamente.";
}

export function ProfileWizard() {
  const router = useRouter();
  const { user } = useAuth();
  const { setSupplier } = useCompany();
  const { currentStep, formData, nextStep, prevStep, goToStep, totalSteps } =
    useProfileWizard();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const adminName = user?.full_name ?? "Usuario";

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = profileSchema.parse(formData);
      const created = await createSupplier(payload);
      setSupplier(created); // Actualiza el estado compartido (sidebar, home)
      setShowSuccess(true);
    } catch (err) {
      console.error("[ProfileWizard] Error al guardar perfil:", err);
      if (mayHaveBeenCreated(err)) {
        // El backend sigue trabajando aunque el navegador corte. Se confirma con
        // reintentos antes de mostrar un error: el 3-sep una única consulta llegó
        // dos segundos antes del commit, recibió 404 y el usuario vio un error
        // por una empresa que sí se había creado.
        const existing = await waitForMySupplier();
        if (existing) {
          setSupplier(existing);
          setShowSuccess(true);
          return;
        }
      }
      setError(errorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (showSuccess) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
          <SuccessView onRedirect={() => router.push("/")} />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <WizardProgress currentStep={currentStep} totalSteps={totalSteps} />
      <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
        {currentStep === 1 && (
          <Step1Identity
            defaultValues={{ legal_name: formData.legal_name, rut: formData.rut }}
            adminName={adminName}
            onNext={(data: Step1Data) => nextStep(data)}
            onBack={prevStep}
          />
        )}
        {currentStep === 2 && (
          <Step2Operations
            defaultValues={{
              regions: formData.regions,
              years_experience: formData.years_experience,
              num_employees: formData.num_employees,
            }}
            onNext={(data: Step2Data) => nextStep(data)}
            onBack={prevStep}
          />
        )}
        {currentStep === 3 && (
          <Step3Specialization
            defaultValues={{
              sectors: formData.sectors,
              keywords: formData.keywords,
              certifications: formData.certifications,
              description: formData.description,
            }}
            onNext={(data: Step3Data) => nextStep(data)}
            onBack={prevStep}
          />
        )}
        {currentStep === 4 && (
          <>
            {error && (
              <div
                role="alert"
                className="mb-6 rounded-md border border-danger/20 bg-danger-soft/30 p-4 text-sm text-danger font-medium"
              >
                {error}
              </div>
            )}
            <Step4Summary
              data={formData}
              onBack={prevStep}
              onSubmit={handleSubmit}
              onGoToStep={goToStep}
              isLoading={isSubmitting}
            />
          </>
        )}
      </div>
    </div>
  );
}
