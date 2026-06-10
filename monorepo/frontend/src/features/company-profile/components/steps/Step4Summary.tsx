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
    <div className="rounded-md border border-border-default bg-white p-5 shadow-xs transition-all hover:shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-bold uppercase tracking-caps text-primary">{title}</h3>
        <button
          type="button"
          onClick={() => onEdit(step)}
          className="text-xs font-bold text-accent hover:text-accent-hover transition-colors focus:outline-none"
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
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-caps text-text-subtle">{label}</span>
      <span className="text-sm font-medium text-text-strong">{value || "—"}</span>
    </div>
  );
}

function TagList({ tags }: { tags: string[] }) {
  if (!tags?.length)
    return <span className="text-sm text-text-subtle italic">No especificado</span>;
  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {tags.map((t) => (
        <span
          key={t}
          className="rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary border border-primary-border/30 shadow-xs"
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
        <h2 className="mb-1 text-2xl font-bold tracking-tight text-text-strong">Revisa tu perfil</h2>
        <p className="text-sm text-text-muted">
          Confirma que todo esté correcto antes de guardar. Podrás editar esta información
          más adelante.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        <Section title="Identidad" step={1} onEdit={onGoToStep}>
          <div className="grid grid-cols-2 gap-4">
            <Row label="Nombre de la empresa" value={data.legal_name ?? ""} />
            <Row label="RUT" value={data.rut ?? ""} />
          </div>
        </Section>

        <Section title="Operación" step={2} onEdit={onGoToStep}>
          <div className="flex flex-col gap-4">
            <div>
              <span className="mb-2 block text-[10px] font-bold uppercase tracking-caps text-text-subtle">Regiones</span>
              <TagList tags={data.regions ?? []} />
            </div>
            <div className="grid grid-cols-2 gap-4 border-t border-border-subtle pt-4">
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
          <div className="flex flex-col gap-4">
            <div>
              <span className="mb-2 block text-[10px] font-bold uppercase tracking-caps text-text-subtle">Rubros</span>
              <TagList tags={data.sectors ?? []} />
            </div>
            {(data.keywords?.length ?? 0) > 0 && (
              <div>
                <span className="mb-2 block text-[10px] font-bold uppercase tracking-caps text-text-subtle">Palabras clave</span>
                <TagList tags={data.keywords ?? []} />
              </div>
            )}
            {(data.certifications?.length ?? 0) > 0 && (
              <div>
                <span className="mb-2 block text-[10px] font-bold uppercase tracking-caps text-text-subtle">Certificaciones</span>
                <TagList tags={data.certifications ?? []} />
              </div>
            )}
            <div className="border-t border-border-subtle pt-4">
              <span className="mb-1 block text-[10px] font-bold uppercase tracking-caps text-text-subtle">Descripción</span>
              <p className="text-sm leading-relaxed text-text-body mt-1">{data.description}</p>
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
