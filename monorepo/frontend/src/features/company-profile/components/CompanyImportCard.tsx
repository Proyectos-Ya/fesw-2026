"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/features/shared/components/Button";
import { Badge } from "@/features/shared/components/Badge";
import { step1Schema } from "../profileSchema";
import {
  describeImportError,
  importCompanyProfile,
  type CompanyProfileImport,
  type ImportErrorDescription,
} from "../services/supplierService";

const SOURCE_NAMES: Record<string, string> = {
  sre: "SRE",
  "web-empresario": "Web Empresario",
  chilerut: "ChileRUT Empresa",
};

interface CompanyImportCardProps {
  rut: string;
  imported: CompanyProfileImport | null;
  onImported: (profile: CompanyProfileImport) => void;
  /** El RUT no pasa la validación local; no se consultó la fuente. */
  onInvalidRut: (message: string) => void;
}

/**
 * Ofrece importar razón social, regiones, rubros y palabras clave desde el RUT
 * escrito en el paso 1. No importa nada por su cuenta: consultar la fuente tiene
 * costo y el usuario decide si quiere la sugerencia. Un RUT inválido no sale del
 * navegador, y ningún error de la fuente bloquea el wizard.
 */
export function CompanyImportCard({
  rut,
  imported,
  onImported,
  onInvalidRut,
}: CompanyImportCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState<ImportErrorDescription | null>(null);

  const handleImport = async () => {
    setNotice(null);
    const validation = step1Schema.shape.rut.safeParse(rut);
    if (!validation.success) {
      onInvalidRut(validation.error.issues[0].message);
      return;
    }
    setIsLoading(true);
    try {
      onImported(await importCompanyProfile(rut));
    } catch (err) {
      console.error("[CompanyImportCard] Error al importar datos:", err);
      setNotice(describeImportError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const sourceName = imported ? (SOURCE_NAMES[imported.source] ?? imported.source) : "";

  return (
    <section
      aria-labelledby="company-import-title"
      className="rounded-md border border-primary-border bg-primary-soft/50 px-5 py-4 shadow-sm"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-white text-primary shadow-xs">
            <Sparkles className="size-4" aria-hidden="true" />
          </div>
          <div className="flex flex-col gap-1">
            {imported ? (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 id="company-import-title" className="text-sm font-bold text-text-strong">
                    Datos importados desde {sourceName}
                  </h3>
                  <Badge tone="success" dot>
                    Listo
                  </Badge>
                </div>
                <p className="text-sm text-text-body">
                  Encontramos a <span className="font-semibold">{imported.legal_name}</span>.
                  Precargamos la razón social, las regiones y los rubros. Revisa y confirma
                  cada uno antes de avanzar; en el paso 3 verás palabras clave sugeridas.
                </p>
              </>
            ) : (
              <>
                <h3 id="company-import-title" className="text-sm font-bold text-text-strong">
                  Importa los datos de tu empresa
                </h3>
                <p className="text-sm text-text-muted">
                  Con el RUT que escribiste buscamos tu empresa en el SII para precargar la razón
                  social, las regiones, los rubros y algunas palabras clave. Podrás revisar cada
                  dato antes de guardar.
                </p>
              </>
            )}
          </div>
        </div>
        <Button
          type="button"
          variant={imported ? "ghost" : "primary"}
          isLoading={isLoading}
          onClick={handleImport}
          className="shrink-0"
        >
          {imported ? "Volver a importar" : "Importar datos"}
        </Button>
      </div>

      {imported && imported.notices.length > 0 && (
        <ul className="mt-3 flex list-disc flex-col gap-1 border-t border-primary-border/60 pt-3 pl-16 text-xs text-text-muted">
          {imported.notices.map((notice) => (
            <li key={notice}>{notice}</li>
          ))}
        </ul>
      )}

      {notice && (
        <div
          role={notice.kind === "info" ? "status" : "alert"}
          className={`mt-3 rounded-md border p-3 text-sm font-medium ${
            notice.kind === "info"
              ? "border-info/20 bg-info-soft/30 text-text-body"
              : "border-danger/20 bg-danger-soft/30 text-danger"
          }`}
        >
          {notice.message}
        </div>
      )}
    </section>
  );
}
