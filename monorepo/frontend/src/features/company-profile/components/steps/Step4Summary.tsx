"use client";

import type { ProfileData } from "../../profileSchema";
import type { WizardStep } from "../../hooks/useProfileWizard";
import { WizardNavigation } from "../WizardNavigation";

interface Step4Props {
  data: Partial<ProfileData>;
  onBack: () => void;
  onSubmit: () => void;
  onGoToStep: (step: WizardStep) => void;
  isLoading: boolean;
}

function Section({
  title,
  step,
  onEdit,
  children,
}: {
  title: string;
  step: WizardStep;
  onEdit: (step: WizardStep) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-input border border-zinc-200 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-brand-primary-900">{title}</h3>
        <button
          type="button"
          onClick={() => onEdit(step)}
          className="text-xs font-medium text-brand-primary-700 hover:text-brand-primary-600 focus:outline-none"
        >
          Editar
        </button>
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-zinc-400">{label}</span>
      <span className="text-sm text-zinc-900">{value || "—"}</span>
    </div>
  );
}

function TagList({ tags }: { tags: string[] }) {
  if (!tags?.length)
    return <span className="text-sm text-zinc-400">No especificado</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((t) => (
        <span
          key={t}
          className="rounded-full bg-brand-primary-100 px-2.5 py-0.5 text-xs font-medium text-brand-primary-900"
        >
          {t}
        </span>
      ))}
    </div>
  );
}

export function Step4Summary({
  data,
  onBack,
  onSubmit,
  onGoToStep,
  isLoading,
}: Step4Props) {
  return (
    <div>
      <div className="mb-6">
        <h2 className="mb-1 text-xl font-bold text-brand-primary-900">Revisa tu perfil</h2>
        <p className="text-sm text-zinc-600">
          Confirma que todo esté correcto antes de guardar. Podrás editar esta información
          más adelante.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <Section title="Identidad" step={1} onEdit={onGoToStep}>
          <div className="grid grid-cols-2 gap-3">
            <Row label="Nombre de la empresa" value={data.legal_name ?? ""} />
            <Row label="RUT" value={data.rut ?? ""} />
          </div>
        </Section>

        <Section title="Operación" step={2} onEdit={onGoToStep}>
          <div className="flex flex-col gap-3">
            <div>
              <span className="mb-1.5 block text-xs text-zinc-400">Regiones</span>
              <TagList tags={data.regions ?? []} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Row
                label="Años de experiencia"
                value={data.years_experience?.toString() ?? ""}
              />
              <Row
                label="Número de empleados"
                value={data.num_employees?.toString() ?? ""}
              />
            </div>
          </div>
        </Section>

        <Section title="Especialización" step={3} onEdit={onGoToStep}>
          <div className="flex flex-col gap-3">
            <div>
              <span className="mb-1.5 block text-xs text-zinc-400">Rubros</span>
              <TagList tags={data.sectors ?? []} />
            </div>
            {(data.keywords?.length ?? 0) > 0 && (
              <div>
                <span className="mb-1.5 block text-xs text-zinc-400">Palabras clave</span>
                <TagList tags={data.keywords ?? []} />
              </div>
            )}
            {(data.certifications?.length ?? 0) > 0 && (
              <div>
                <span className="mb-1.5 block text-xs text-zinc-400">Certificaciones</span>
                <TagList tags={data.certifications ?? []} />
              </div>
            )}
            <div>
              <span className="mb-1 block text-xs text-zinc-400">Descripción</span>
              <p className="text-sm leading-relaxed text-zinc-900">{data.description}</p>
            </div>
          </div>
        </Section>
      </div>

      <WizardNavigation
        onBack={onBack}
        onNext={onSubmit}
        isFirstStep={false}
        isLastStep
        isLoading={isLoading}
      />
    </div>
  );
}
