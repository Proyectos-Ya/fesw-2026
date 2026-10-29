"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { step3Schema, type Step3Data } from "../../profileSchema";
import { Textarea } from "@/features/shared/components/Textarea";
import { TagInput } from "@/features/shared/components/TagInput";
import { Button } from "@/features/shared/components/Button";
import { WizardNavigation } from "../WizardNavigation";
import { ImportedFieldReview, isFieldLocked, type FieldReview } from "../ImportedFieldReview";
import { KeywordSuggestions } from "../KeywordSuggestions";
import { CertificationListInput } from "../CertificationListInput";
import { SectorSelect } from "../SectorSelect";
import { suggestKeywordsFromDescription } from "../../services/supplierService";

const SUGGEST_ERROR =
  "No pudimos sugerir palabras clave. Inténtalo nuevamente o agrégalas a mano.";

const normalize = (keyword: string) => keyword.trim().toLocaleLowerCase("es");

interface Step3Props {
  defaultValues: Partial<Step3Data>;
  /** Palabras clave importadas desde el RUT, ofrecidas como sugerencias. */
  suggestedKeywords?: string[];
  sectorsReview: FieldReview;
  /** Rubros que sumó la importación; "Borrar" quita solo estos. */
  addedSectors: string[];
  /** "Siguiente" queda bloqueado mientras los rubros importados no se confirman. */
  nextBlocked: boolean;
  /** Sugerencias descartadas; el wizard las guarda para que no vuelvan al regresar a este paso. */
  dismissedKeywords?: string[];
  onDismissKeyword?: (keyword: string) => void;
  onNext: (data: Step3Data) => void;
  onBack: () => void;
}

export function Step3Specialization({
  defaultValues,
  suggestedKeywords = [],
  sectorsReview,
  addedSectors,
  nextBlocked,
  dismissedKeywords = [],
  onDismissKeyword,
  onNext,
  onBack,
}: Step3Props) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    getValues,
    setValue,
    formState: { errors },
  } = useForm<Step3Data>({
    resolver: zodResolver(step3Schema),
    defaultValues: {
      sectors: [],
      keywords: [],
      certifications: [],
      description: "",
      ...defaultValues,
    },
  });

  const description = watch("description");
  const keywords = watch("keywords");

  // Sugerencias sacadas de la descripción; las del RUT llegan por `suggestedKeywords`.
  const [descriptionSuggestions, setDescriptionSuggestions] = useState<string[]>([]);
  // Para avisar solo cuando la respuesta vino vacía, no cuando el usuario descartó todas.
  const [noNewSuggestions, setNoNewSuggestions] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);

  const handleSuggest = async () => {
    setIsSuggesting(true);
    setSuggestError(null);
    try {
      const found = await suggestKeywordsFromDescription(
        getValues("description"),
        getValues("keywords"),
      );
      setDescriptionSuggestions(found);
      setNoNewSuggestions(found.length === 0);
    } catch (err) {
      console.error("[Step3Specialization] Error al sugerir palabras clave:", err);
      setSuggestError(SUGGEST_ERROR);
    } finally {
      setIsSuggesting(false);
    }
  };

  const addKeywords = (added: string[]) => {
    const current = getValues("keywords");
    const taken = new Set(current.map(normalize));
    const next = added.filter((keyword) => !taken.has(normalize(keyword)));
    setValue("keywords", [...current, ...next], { shouldDirty: true, shouldValidate: true });
  };

  const dismissDescriptionSuggestion = (keyword: string) => {
    onDismissKeyword?.(keyword);
    setDescriptionSuggestions((current) =>
      current.filter((item) => normalize(item) !== normalize(keyword)),
    );
  };

  const handleClearSectors = () => {
    sectorsReview.onClear();
    const remaining = (getValues("sectors") ?? []).filter((s) => !addedSectors.includes(s));
    setValue("sectors", remaining, { shouldDirty: true });
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="mb-1 text-2xl font-bold tracking-tight text-text-strong">Especialización</h2>
        <p className="text-sm text-text-muted">
          Esta información es la base del motor de matching. Mientras más detallada, mejores
          serán las recomendaciones.
        </p>
      </div>

      <div className="flex flex-col gap-8">
        <Controller
          name="sectors"
          control={control}
          render={({ field }) => (
            <div className="flex flex-col gap-3">
              <SectorSelect
                selected={field.value}
                onChange={field.onChange}
                error={errors.sectors?.message}
                disabled={isFieldLocked(sectorsReview.status)}
              />
              <ImportedFieldReview
                fieldLabel="rubros"
                {...sectorsReview}
                onClear={handleClearSectors}
              />
            </div>
          )}
        />

        <Controller
          name="keywords"
          control={control}
          render={({ field }) => (
            <div className="flex flex-col gap-3">
              <TagInput
                label="Palabras clave de experiencia"
                tags={field.value}
                onChange={field.onChange}
                placeholder="Ej: luminarias LED, pavimentación, redes húmedas..."
                hint="Presiona Enter o coma para añadir. Mejoran la precisión del match."
                error={errors.keywords?.message}
              />
              <KeywordSuggestions
                suggestions={suggestedKeywords}
                selected={field.value}
                dismissed={dismissedKeywords}
                onDismiss={onDismissKeyword}
                onAdd={(keywords) => field.onChange([...field.value, ...keywords])}
              />
            </div>
          )}
        />

        <Controller
          name="certifications"
          control={control}
          render={({ field }) => (
            <CertificationListInput
              label="Certificaciones relevantes"
              value={field.value}
              onChange={field.onChange}
              hint="Presiona Enter en el nombre o el botón Agregar. La fecha de vencimiento es opcional."
              error={errors.certifications?.message}
              optional
            />
          )}
        />

        <Textarea
          label="Descripción de la empresa"
          placeholder="Ej: Constructora especializada en obras civiles menores y mantención de infraestructura municipal..."
          hint="Describe qué hace tu empresa y en qué se especializa."
          charCount={description?.length ?? 0}
          maxChars={1000}
          error={errors.description?.message}
          {...register("description")}
        />

        <div className="-mt-4 flex flex-col gap-3">
          <div>
            <Button
              type="button"
              variant="ghost"
              onClick={handleSuggest}
              isLoading={isSuggesting}
              disabled={isSuggesting || !description?.trim()}
            >
              <Sparkles className="size-4" aria-hidden="true" />
              Sugerir palabras clave desde la descripción
            </Button>
          </div>
          {suggestError && (
            <p role="alert" className="text-sm font-medium text-danger">
              {suggestError}
            </p>
          )}
          <KeywordSuggestions
            suggestions={descriptionSuggestions}
            selected={keywords}
            dismissed={dismissedKeywords}
            onAdd={addKeywords}
            onDismiss={dismissDescriptionSuggestion}
            hint="Salen de la descripción que escribiste. Agrega solo las que describan lo que realmente haces."
          />
          {noNewSuggestions && (
            <p className="text-sm text-text-muted">
              No encontramos palabras clave nuevas en la descripción.
            </p>
          )}
        </div>
      </div>

      <WizardNavigation
        onBack={onBack}
        onNext={handleSubmit(onNext)}
        isFirstStep={false}
        isLastStep={false}
        nextDisabled={nextBlocked}
      />
    </div>
  );
}
