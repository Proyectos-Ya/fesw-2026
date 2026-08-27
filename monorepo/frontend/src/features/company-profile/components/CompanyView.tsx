"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { profileSchema } from "../profileSchema";
import { REGIONS } from "../data/regions";
import { SECTORS } from "../data/sectors";
import { useCompany } from "./CompanyProvider";
import { updateSupplier, type Supplier } from "../services/supplierService";
import { parseApiDate } from "@/features/matches/utils/format";
import { Input } from "@/features/shared/components/Input";
import { Textarea } from "@/features/shared/components/Textarea";
import { ChipSelect } from "@/features/shared/components/ChipSelect";
import { TagInput } from "@/features/shared/components/TagInput";
import { Button } from "@/features/shared/components/Button";
import { ApiError, TimeoutError } from "@/features/shared/api/client";

// El RUT no es editable (identidad tributaria de la empresa)
const companyEditSchema = profileSchema.omit({ rut: true });

type CompanyEditData = z.infer<typeof companyEditSchema>;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-bold uppercase tracking-caps text-text-subtle mb-1">
        {label}
      </div>
      <div className="text-sm text-text-strong">{children}</div>
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

function CompanyDetails({
  supplier,
  onEdit,
}: {
  supplier: Supplier;
  onEdit: () => void;
}) {
  return (
    <div className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle">
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-strong">
            {supplier.legal_name}
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {supplier.trade_name ?? "Sin nombre de fantasía"} · RUT {supplier.rut}
          </p>
        </div>
        <Button variant="primary" onClick={onEdit} className="font-bold">
          Editar
        </Button>
      </div>

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
        <Field label="Palabras clave">
          <ChipList items={supplier.keywords} />
        </Field>
        <Field label="Certificaciones">
          <ChipList items={supplier.certifications} />
        </Field>
        <Field label="Miembro desde">
          {parseApiDate(supplier.created_at)?.toLocaleDateString("es-CL", {
            year: "numeric",
            month: "long",
            day: "numeric",
          }) ?? "—"}
        </Field>
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
      className="rounded-lg bg-white p-8 shadow-premium border border-border-subtle flex flex-col gap-6"
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
          <ChipSelect
            label="Rubros principales"
            options={SECTORS}
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
          <TagInput
            label="Certificaciones"
            tags={field.value}
            onChange={field.onChange}
            placeholder="Ej: ISO 9001"
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

export function CompanyView() {
  const { company, setSupplier } = useCompany();
  const [isEditing, setIsEditing] = useState(false);

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
          className="mt-8 rounded-full bg-primary px-8 py-3 text-sm font-bold text-white transition-all hover:bg-primary-hover"
        >
          Crear mi empresa
        </Link>
      </section>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
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
        <CompanyDetails
          supplier={company.supplier}
          onEdit={() => setIsEditing(true)}
        />
      )}
    </div>
  );
}
