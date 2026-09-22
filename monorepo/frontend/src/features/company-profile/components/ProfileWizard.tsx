"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/features/auth/AuthContext";
import { useProfileWizard } from "../hooks/useProfileWizard";
import { WizardProgress } from "@/features/shared/components/WizardProgress";
import { Step1Identity } from "./steps/Step1Identity";
import { Step2Operations } from "./steps/Step2Operations";
import { Step3Specialization } from "./steps/Step3Specialization";
import { Step4Summary } from "./steps/Step4Summary";
import { z } from "zod";
import { formatRut, profileSchema } from "../profileSchema";
import type { Step1Data, Step2Data, Step3Data } from "../profileSchema";
import { createSupplier, waitForMySupplier } from "../services/supplierService";
import { useCompany } from "./CompanyProvider";
import { CreatingCompanyView } from "./CreatingCompanyView";
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
  // Timeout o corte de red: no hubo respuesta, así que no se sabe qué pasó.
  return true;
}

/**
 * `waitForMySupplier` devuelve la empresa del usuario, sea cual sea. Un 409
 * puede significar "ya tenías otra empresa", no "la tuya se creó igual", y ahí
 * dar el envío por bueno descartaría en silencio el perfil recién escrito.
 *
 * Se compara en formato canónico, con el mismo criterio que el backend: el RUT
 * guardado puede venir con puntos y el escrito sin ellos, y es el mismo.
 */
function esLaEmpresaEnviada(rutEncontrado: string, rutEnviado: string): boolean {
  return formatRut(rutEncontrado) === formatRut(rutEnviado);
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof z.ZodError) {
    return "Hay campos incompletos o inválidos. Revisa los pasos anteriores.";
  }
  if (err instanceof TimeoutError) return err.message;
  return "No se pudo guardar el perfil. Verifica tu conexión e inténtalo nuevamente.";
}

/**
 * `creating` y `verifying` muestran la pantalla de espera; `idle` el resumen,
 * con el error si lo hubo. Un solo estado evita combinaciones sin sentido, como
 * "enviando" y "éxito" a la vez.
 */
type SubmitState = "idle" | "creating" | "verifying" | "success";

export function ProfileWizard() {
  const { user } = useAuth();
  const { setSupplier } = useCompany();
  const {
    currentStep,
    formData,
    importedProfile,
    nextStep,
    prevStep,
    goToStep,
    applyImport,
    totalSteps,
  } = useProfileWizard();
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [error, setError] = useState<string | null>(null);

  const adminName = user?.full_name ?? "Usuario";
  const isBusy = submitState === "creating" || submitState === "verifying";

  // Recargar o cerrar a mitad de la creación deja la petición corriendo en el
  // backend sin nadie esperándola, y el reintento que sigue es justo lo que
  // terminó en el 409 del 3-sep. Mientras se crea, el navegador pide confirmación.
  useEffect(() => {
    if (!isBusy) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [isBusy]);

  const handleSubmit = async () => {
    setError(null);

    // Se valida antes de mostrar la espera: con datos inválidos la petición ni
    // siquiera sale, y la pantalla de carga solo parpadearía.
    const parsed = profileSchema.safeParse(formData);
    if (!parsed.success) {
      setError(errorMessage(parsed.error));
      return;
    }

    // Antes de cualquier await: la pantalla de espera aparece en el mismo clic.
    setSubmitState("creating");
    try {
      const created = await createSupplier(parsed.data);
      setSupplier(created); // Actualiza el estado compartido (sidebar, home)
      setSubmitState("success");
    } catch (err) {
      console.error("[ProfileWizard] Error al guardar perfil:", err);
      if (mayHaveBeenCreated(err)) {
        // El backend sigue trabajando aunque el navegador corte. Se confirma con
        // reintentos antes de mostrar un error: el 3-sep una única consulta llegó
        // dos segundos antes del commit, recibió 404 y el usuario vio un error
        // por una empresa que sí se había creado.
        setSubmitState("verifying");
        const existing = await waitForMySupplier();
        if (existing && esLaEmpresaEnviada(existing.rut, parsed.data.rut)) {
          setSupplier(existing);
          setSubmitState("success");
          return;
        }
      }
      setError(errorMessage(err));
      setSubmitState("idle");
    }
  };

  if (submitState === "success") {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
          <SuccessView onRedirect={() => { window.location.href = "/"; }} />
        </div>
      </div>
    );
  }

  if (submitState === "creating" || submitState === "verifying") {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
          <CreatingCompanyView phase={submitState} />
        </div>
      </div>
    );
  }

  if (submitState === "creating" || submitState === "verifying") {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
          <CreatingCompanyView phase={submitState} />
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
            rut={formData.rut}
            importedProfile={importedProfile}
            onImported={applyImport}
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
            suggestedKeywords={importedProfile?.keywords}
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
              isLoading={isBusy}
            />
          </>
        )}
      </div>
    </div>
  );
}
