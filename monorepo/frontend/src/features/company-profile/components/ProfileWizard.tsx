"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useProfileWizard } from "../hooks/useProfileWizard";
import { WizardProgress } from "@/features/shared/components/WizardProgress";
import { Step1Identity } from "./steps/Step1Identity";
import { Step2Operations } from "./steps/Step2Operations";
import { Step3Specialization } from "./steps/Step3Specialization";
import { Step4Summary } from "./steps/Step4Summary";
import { z } from "zod";
import { profileSchema } from "../profileSchema";
import type { Step1Data, Step2Data, Step3Data } from "../profileSchema";
import { createSupplier } from "../services/supplierService";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { useSession } from "@/features/auth/components/SessionProvider";

export function ProfileWizard() {
  const router = useRouter();
  const { user } = useSession();
  const { currentStep, formData, nextStep, prevStep, goToStep, totalSteps } =
    useProfileWizard();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = profileSchema.parse(formData);
      await createSupplier(payload);
      router.push("/");
    } catch (err) {
      console.error("[ProfileWizard] Error al guardar perfil:", err);
      if (err instanceof TimeoutError) {
        setError(err.message);
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof z.ZodError) {
        setError("Hay campos incompletos o inválidos. Revisa los pasos anteriores.");
      } else {
        setError(
          "No se pudo guardar el perfil. Verifica tu conexión e inténtalo nuevamente.",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl">
      <WizardProgress currentStep={currentStep} totalSteps={totalSteps} />
      <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
        {currentStep === 1 && (
          <Step1Identity
            defaultValues={{ legal_name: formData.legal_name, rut: formData.rut }}
            adminName={user?.full_name ?? ""}
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
