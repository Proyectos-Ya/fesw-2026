"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  formatCertificationDate,
  normalizeCertification,
  profileSchema,
  type CertificationItem,
} from "../profileSchema";
import { getCertificationStatus } from "../utils/certification";
import { CertificationListInput } from "./CertificationListInput";
import { REGIONS } from "../data/regions";
import { SectorSelect } from "./SectorSelect";
import { useCompany } from "./CompanyProvider";
import {
  updateSupplier,
  validateCompanyLogoFile,
  type Supplier,
} from "../services/supplierService";
import { parseApiDate } from "@/features/matches/utils/format";
import { Avatar } from "@/features/shared/components/Avatar";
import { Icon } from "@/features/shared/components/Icon";
import { Input } from "@/features/shared/components/Input";
import { Textarea } from "@/features/shared/components/Textarea";
import { ChipSelect } from "@/features/shared/components/ChipSelect";
import { TagInput } from "@/features/shared/components/TagInput";
import { Button } from "@/features/shared/components/Button";
import { Badge } from "@/features/shared/components/Badge";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { CompanyTeamSection } from "./CompanyTeamSection";
import { ExtensionPairingSection } from "./ExtensionPairingSection";
import { WorkspaceMatchThresholdSettings } from "@/features/workspaces/components/WorkspaceMatchThresholdSettings";
import { WorkspaceExportsPanel } from "@/features/tender-export/components/WorkspaceExportsPanel";

// El RUT no es editable (identidad tributaria de la empresa)
const companyEditSchema = profileSchema.omit({ rut: true });

type CompanyEditData = z.infer<typeof companyEditSchema>;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-bold uppercase tracking-caps text-text-subtle mb-1">
        {label}
      </div>
      {/* break-words: el mismo texto libre del perfil se muestra acá, y sin esto
          una palabra larga sin espacios desborda la tarjeta. */}
      <div className="text-sm text-text-strong break-words">{children}</div>
    </div>
  );
}

function ChipList({ items }: { items: string[] | undefined }) {
  if (!items || items.length === 0) {
    return <span className="text-text-subtle">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full bg-primary-soft px-3 py-1 text-xs font-semibold text-primary"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

const STATUS_BADGE_TONE = {
  expired: "danger",
  expiring_soon: "warning",
} as const;

function CertificationsField({
  supplier,
  onSaved,
}: {
  supplier: Supplier;
  onSaved: (supplier: Supplier) => void;
}) {
  const items = (supplier.certifications ?? []).map(normalizeCertification);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [deletingIndex, setDeletingIndex] = useState<number | null>(null);
  const [draftDate, setDraftDate] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const closeControls = () => {
    setEditingIndex(null);
    setDeletingIndex(null);
    setError(null);
  };

  const save = async (certifications: CertificationItem[]) => {
    setIsSaving(true);
    setError(null);
    try {
      const updated = await updateSupplier({ certifications });
      onSaved(updated);
      setEditingIndex(null);
      setDeletingIndex(null);
    } catch (err) {
      if (err instanceof ApiError || err instanceof TimeoutError) {
        setError(err.message);
      } else {
        setError("No se pudo guardar la certificación. Inténtalo nuevamente.");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const startEditing = (index: number) => {
    setDeletingIndex(null);
    setError(null);
    setDraftDate(items[index].expires_at ?? "");
    setEditingIndex(index);
  };

  const startDeleting = (index: number) => {
    setEditingIndex(null);
    setError(null);
    setDeletingIndex(index);
  };

  const saveDate = (index: number) =>
    save(
      items.map((item, i) =>
        i === index ? { ...item, expires_at: draftDate || null } : item,
      ),
    );

  const remove = (index: number) => save(items.filter((_, i) => i !== index));

  if (items.length === 0) return <span className="text-text-subtle">—</span>;

  return (
    <div className="flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {items.map((item, index) => {
          const certStatus = getCertificationStatus(item.expires_at);
          const tone =
            certStatus.status === "expired" || certStatus.status === "expiring_soon"
              ? STATUS_BADGE_TONE[certStatus.status]
              : null;
          return (
            <li
              key={`${item.name}-${index}`}
              className="rounded-md border border-border-default bg-surface-card px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="font-medium text-text-strong break-words">
                    {item.name}
                  </span>
                  {item.expires_at && (
                    <span className="text-xs text-text-muted">
                      Vence: {formatCertificationDate(item.expires_at)}
                    </span>
                  )}
                  {tone && <Badge tone={tone}>{certStatus.label}</Badge>}
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => startEditing(index)}
                    disabled={isSaving}
                    aria-label={`Editar fecha de ${item.name}`}
                  >
                    Editar fecha
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => startDeleting(index)}
                    disabled={isSaving}
                    aria-label={`Eliminar ${item.name}`}
                  >
                    Eliminar
                  </Button>
                </div>
              </div>

              {editingIndex === index && (
                <div className="mt-3 flex flex-wrap items-end gap-3">
                  <Input
                    type="date"
                    label={`Fecha de vencimiento de ${item.name}`}
                    value={draftDate}
                    onChange={(e) => setDraftDate(e.target.value)}
                    disabled={isSaving}
                  />
                  <Button
                    type="button"
                    variant="primary"
                    onClick={() => saveDate(index)}
                    isLoading={isSaving}
                  >
                    Guardar fecha
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={closeControls}
                    disabled={isSaving}
                  >
                    Cancelar
                  </Button>
                </div>
              )}

              {deletingIndex === index && (
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <span className="text-sm text-text-strong">
                    ¿Eliminar esta certificación?
                  </span>
                  <Button
                    type="button"
                    variant="primary"
                    onClick={() => remove(index)}
                    isLoading={isSaving}
                  >
                    Confirmar eliminación
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={closeControls}
                    disabled={isSaving}
                  >
                    Cancelar
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {error && (
        <div
          role="alert"
          className="p-3 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium"
        >
          {error}
        </div>
      )}
    </div>
  );
}

function CompanyLogoUploadSection({
  supplier,
  onLogoUpdated,
  compact = false,
}: {
  supplier: Supplier;
  onLogoUpdated?: (supplier: Supplier) => void;
  compact?: boolean;
}) {
  const { logoUrl, uploadLogo } = useCompany();
  const [logoError, setLogoError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const currentLogo = logoUrl ?? supplier.logo_url ?? null;

  const handleLogoChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLogoError(null);
    setIsUploading(true);
    try {
      const result = await uploadLogo(file);
      if (!result.ok) {
        setLogoError(result.error ?? "Formato inválido o archivo muy pesado");
      } else if (result.supplier) {
        onLogoUpdated?.(result.supplier);
      }
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  };

  if (compact) {
    return (
      <div className="flex flex-col items-center md:items-start gap-2 shrink-0">
        <label
          htmlFor="company-logo-input"
          title="Cambiar logo corporativo (PNG o JPG, máx. 5MB)"
          className={`relative group size-24 rounded-xl overflow-hidden block ${
            isUploading ? "cursor-not-allowed opacity-70" : "cursor-pointer"
          }`}
        >
          <Avatar
            name={supplier.trade_name || supplier.legal_name}
            src={currentLogo ?? undefined}
            size="xl"
            shape="square"
            className="w-full h-full"
          />
          <div
            className={`absolute inset-0 flex items-center justify-center bg-black/50 text-white transition-opacity duration-200 ${
              isUploading ? "opacity-100" : "opacity-0 group-hover:opacity-100"
            }`}
          >
            <Icon name="camera" size={24} color="#FFFFFF" />
          </div>
          <input
            id="company-logo-input"
            data-testid="company-logo-input"
            type="file"
            accept="image/png,image/jpeg"
            onChange={handleLogoChange}
            disabled={isUploading}
            className="sr-only"
            aria-label="Subir logo corporativo"
          />
        </label>
        {logoError && (
          <div
            role="alert"
            data-testid="company-logo-error"
            className="max-w-xs rounded-md border border-danger bg-danger-soft px-3 py-2 text-xs font-semibold text-danger-text"
          >
            {logoError}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-4">
        <Avatar
          name={supplier.trade_name || supplier.legal_name}
          src={currentLogo ?? undefined}
          size="lg"
          shape="square"
        />
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="company-logo-input"
            className={`inline-flex w-fit cursor-pointer items-center gap-2 rounded-lg border border-border-default bg-surface-inset px-3 py-1.5 text-xs font-semibold text-text-strong transition-colors ${
              isUploading
                ? "opacity-60 cursor-not-allowed"
                : "hover:bg-surface-hover"
            }`}
          >
            {isUploading ? "Subiendo..." : "Subir logo"}
            <input
              id="company-logo-input"
              data-testid="company-logo-input"
              type="file"
              accept="image/png,image/jpeg"
              onChange={handleLogoChange}
              disabled={isUploading}
              className="sr-only"
              aria-label="Subir logo corporativo"
            />
          </label>
          <span className="text-xs text-text-subtle">
            Formatos permitidos: PNG o JPG (máx. 5MB)
          </span>
        </div>
      </div>

      {logoError && (
        <div
          role="alert"
          data-testid="company-logo-error"
          className="rounded-md border border-danger bg-danger-soft px-4 py-3 text-sm font-semibold text-danger-text"
        >
          {logoError}
        </div>
      )}
    </div>
  );
}

function CompanyHeroCard({
  supplier,
  onEdit,
  onSupplierChange,
}: {
  supplier: Supplier;
  onEdit: () => void;
  onSupplierChange: (supplier: Supplier) => void;
}) {
  const memberSince =
    parseApiDate(supplier.created_at)?.toLocaleDateString("es-CL", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }) ?? "—";

  return (
    <div className="mb-6 rounded-lg bg-surface-card p-6 sm:p-8 shadow-premium border border-border-subtle">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-5">
        <div className="flex flex-col md:flex-row md:items-center gap-5 min-w-0 flex-1">
          <CompanyLogoUploadSection
            supplier={supplier}
            onLogoUpdated={(updatedSupplier) => onSupplierChange(updatedSupplier)}
            compact
          />
          <div className="flex flex-col gap-1 min-w-0 flex-1">
            <h1 className="m-0 text-2xl sm:text-3xl font-bold tracking-tight text-text-strong break-words">
              {supplier.legal_name}
            </h1>
            <p className="m-0 text-sm text-text-muted break-words">
              {supplier.trade_name ?? "Sin nombre de fantasía"} · RUT {supplier.rut}
            </p>
            <div className="inline-flex items-center gap-1.5 text-xs text-text-subtle">
              <Icon name="calendar" size={14} />
              <span>Miembro desde {memberSince}</span>
            </div>
          </div>
        </div>
        <Button
          variant="primary"
          onClick={onEdit}
          className="font-bold self-start shrink-0"
        >
          Editar
        </Button>
      </div>
    </div>
  );
}

function CompanyDetails({
  supplier,
  onSupplierChange,
}: {
  supplier: Supplier;
  onSupplierChange: (supplier: Supplier) => void;
}) {
  const [showKeywords, setShowKeywords] = useState(false);
  const keywordsCount = supplier.keywords?.length ?? 0;

  return (
    <div className="rounded-lg bg-surface-card p-6 sm:p-8 shadow-premium border border-border-subtle">
      <div className="flex flex-col gap-6">
        <Field label="Descripción">
          {supplier.description || <span className="text-text-subtle">—</span>}
        </Field>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <Field label="Años de experiencia">{supplier.years_experience}</Field>
          <Field label="Número de empleados">{supplier.num_employees}</Field>
        </div>
        <Field label="Regiones donde opera">
          <ChipList items={supplier.regions} />
        </Field>
        <Field label="Rubros">
          <ChipList items={supplier.sectors} />
        </Field>
        <Field label="Certificaciones">
          <CertificationsField supplier={supplier} onSaved={onSupplierChange} />
        </Field>
        <div className="border-t border-border-subtle pt-4">
          <button
            type="button"
            onClick={() => setShowKeywords((prev) => !prev)}
            aria-expanded={showKeywords}
            className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-md py-1 text-left transition-colors hover:text-text-strong"
          >
            <span className="text-xs font-bold uppercase tracking-caps text-text-subtle">
              Palabras clave ({keywordsCount})
            </span>
            <Icon
              name={showKeywords ? "chevron-up" : "chevron-down"}
              size={16}
              className="text-text-subtle"
            />
          </button>
          {showKeywords && (
            <div className="mt-3">
              <ChipList items={supplier.keywords} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CompanyEditForm({
  supplier,
  onSaved,
  onCancel,
}: {
  supplier: Supplier;
  onSaved: (supplier: Supplier) => void;
  onCancel: () => void;
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<CompanyEditData>({
    resolver: zodResolver(companyEditSchema),
    defaultValues: {
      legal_name: supplier.legal_name,
      trade_name: supplier.trade_name ?? "",
      description: supplier.description ?? "",
      regions: supplier.regions ?? [],
      sectors: supplier.sectors ?? [],
      keywords: supplier.keywords ?? [],
      certifications: supplier.certifications ?? [],
      years_experience: supplier.years_experience,
      num_employees: supplier.num_employees,
    },
  });

  const description = watch("description");

  const onSubmit = async (data: CompanyEditData) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await updateSupplier({
        ...data,
        trade_name: data.trade_name?.trim() ? data.trade_name.trim() : null,
      });
      onSaved(updated);
    } catch (err) {
      if (err instanceof ApiError || err instanceof TimeoutError) {
        setError(err.message);
      } else {
        setError("No se pudo guardar la empresa. Inténtalo nuevamente.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-lg bg-surface-card p-6 sm:p-8 shadow-premium border border-border-subtle flex flex-col gap-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-strong">
            Editar empresa
          </h1>
          <p className="text-sm text-text-muted mt-1">
            RUT {supplier.rut} (no editable)
          </p>
        </div>
      </div>

      <div className="pb-4 border-b border-border-subtle">
        <CompanyLogoUploadSection supplier={supplier} />
      </div>

      {error && (
        <div className="p-4 rounded-md bg-danger-soft/30 border border-danger/20 text-danger text-sm font-medium">
          {error}
        </div>
      )}

      <Input
        label="Razón social"
        error={errors.legal_name?.message}
        {...register("legal_name")}
      />

      <Input
        label="Nombre de fantasía (opcional)"
        placeholder="Ej: Constructora Norte"
        error={errors.trade_name?.message}
        {...register("trade_name")}
      />

      <Textarea
        label="Descripción"
        rows={5}
        charCount={description?.length ?? 0}
        maxChars={1000}
        error={errors.description?.message}
        {...register("description")}
      />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Input
          label="Años de experiencia"
          type="number"
          error={errors.years_experience?.message}
          {...register("years_experience", { valueAsNumber: true })}
        />
        <Input
          label="Número de empleados"
          type="number"
          error={errors.num_employees?.message}
          {...register("num_employees", { valueAsNumber: true })}
        />
      </div>

      <Controller
        name="regions"
        control={control}
        render={({ field }) => (
          <ChipSelect
            label="Regiones donde opera"
            options={REGIONS}
            selected={field.value}
            onChange={field.onChange}
            error={errors.regions?.message}
          />
        )}
      />

      <Controller
        name="sectors"
        control={control}
        render={({ field }) => (
          <SectorSelect
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
            placeholder="Ej: luminarias LED, pavimentación..."
            hint="Presiona Enter o coma para añadir."
            error={errors.keywords?.message}
          />
        )}
      />

      <Controller
        name="certifications"
        control={control}
        render={({ field }) => (
          <CertificationListInput
            label="Certificaciones"
            value={field.value}
            onChange={field.onChange}
            optional
            error={errors.certifications?.message}
          />
        )}
      />

      <div className="flex justify-end gap-3 pt-2">
        <Button
          type="button"
          variant="ghost"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancelar
        </Button>
        <Button
          type="submit"
          variant="primary"
          className="font-bold"
          isLoading={isSubmitting}
        >
          Guardar cambios
        </Button>
      </div>
    </form>
  );
}

export type CompanyTab = "informacion" | "equipo";

export function CompanyView() {
  const { company, setSupplier } = useCompany();
  const [isEditing, setIsEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<CompanyTab>("informacion");

  if (company.status === "loading") return null;

  if (company.status === "error") {
    return (
      <section className="flex flex-1 items-center justify-center py-12">
        <p className="text-text-muted">
          No pudimos cargar tu empresa. Recarga la página para intentarlo
          nuevamente.
        </p>
      </section>
    );
  }

  if (company.status === "without-company") {
    return (
      <section className="flex flex-1 flex-col items-center justify-center text-center py-24">
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-text-strong">
          Aún no tienes una empresa
        </h1>
        <p className="mt-4 max-w-md text-text-muted leading-relaxed">
          Crea el perfil de tu empresa para empezar a recibir licitaciones
          compatibles.
        </p>
        <Link
          href="/empresa/crear"
          className="mt-8 rounded-full bg-primary px-8 py-3 text-sm font-bold text-on-primary transition-all hover:bg-primary-hover"
        >
          Crear mi empresa
        </Link>
      </section>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      {isEditing ? (
        <CompanyEditForm
          supplier={company.supplier}
          onSaved={(updated) => {
            setSupplier(updated);
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <>
          <CompanyHeroCard
            supplier={company.supplier}
            onEdit={() => setIsEditing(true)}
            onSupplierChange={setSupplier}
          />

          <div
            role="tablist"
            aria-label="Secciones del perfil de empresa"
            className="mb-6 flex gap-2 border-b border-border-subtle"
          >
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "informacion"}
              onClick={() => setActiveTab("informacion")}
              className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "informacion"
                  ? "border-primary text-primary"
                  : "border-transparent text-text-muted hover:text-text-strong"
              }`}
            >
              <Icon name="building-2" className="size-4" />
              Información
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "equipo"}
              onClick={() => setActiveTab("equipo")}
              className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-semibold transition-all cursor-pointer ${
                activeTab === "equipo"
                  ? "border-primary text-primary"
                  : "border-transparent text-text-muted hover:text-text-strong"
              }`}
            >
              <Icon name="users" className="size-4" />
              Equipo
            </button>
          </div>

          {activeTab === "informacion" && (
            <>
              <CompanyDetails
                supplier={company.supplier}
                onSupplierChange={setSupplier}
              />
              <ExtensionPairingSection supplierId={company.supplier.id} />
            </>
          )}

          {activeTab === "equipo" && (
            <>
              <CompanyTeamSection
                supplierId={company.supplier.id}
                supplierName={
                  company.supplier.trade_name || company.supplier.legal_name
                }
              />
              <WorkspaceMatchThresholdSettings supplierId={company.supplier.id} />
              <section className="pt-4 border-t border-border-subtle">
                <h3 className="text-sm font-semibold text-text-strong mb-3">
                  Documentos del equipo
                </h3>
                <WorkspaceExportsPanel />
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
