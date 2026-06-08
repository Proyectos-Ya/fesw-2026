"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useProfileWizard } from "../hooks/useProfileWizard";
import { WizardProgress } from "@/features/shared/components/WizardProgress";
import { Step1Identity } from "./steps/Step1Identity";
import { Step2Operations } from "./steps/Step2Operations";
import { Step3Specialization } from "./steps/Step3Specialization";
import { Step4Summary } from "./steps/Step4Summary";
import type { Step1Data, Step2Data, Step3Data } from "../profileSchema";

const PLACEHOLDER_ADMIN = "Usuario Demo";

export function ProfileWizard() {
  const router = useRouter();
  const { currentStep, formData, nextStep, prevStep, goToStep, totalSteps } =
    useProfileWizard();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 800));
      router.push("/?as=ready");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl">
      <WizardProgress currentStep={currentStep} totalSteps={totalSteps} />
      <div className="rounded-card bg-white p-8 shadow-premium">
        {currentStep === 1 && (
          <Step1Identity
            defaultValues={{ legal_name: formData.legal_name, rut: formData.rut }}
            adminName={PLACEHOLDER_ADMIN}
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
          <Step4Summary
            data={formData}
            onBack={prevStep}
            onSubmit={handleSubmit}
            onGoToStep={goToStep}
            isLoading={isSubmitting}
          />
        )}
      </div>
    </div>
  );
}
