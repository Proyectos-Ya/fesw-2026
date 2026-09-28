"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/features/shared/components/Button";
import { Badge } from "@/features/shared/components/Badge";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import {
  importCompanyProfile,
  type CompanyProfileImport,
} from "../services/supplierService";

const SOURCE_NAMES: Record<string, string> = {
  sre: "SRE",
  "web-empresario": "Web Empresario",
};

interface CompanyImportCardProps {
  rut: string;
  imported: CompanyProfileImport | null;
  onImported: (profile: CompanyProfileImport) => void;
}

/**
 * Ofrece importar regiones, rubros y palabras clave desde el RUT validado en el
 * paso anterior. No importa nada por su cuenta: consultar la fuente tiene costo
 * y el usuario decide si quiere la sugerencia.
 */
export function CompanyImportCard({ rut, imported, onImported }: CompanyImportCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleImport = async () => {
    setIsLoading(true);
    setError(null);
    try {
      onImported(await importCompanyProfile(rut));
    } catch (err) {
      console.error("[CompanyImportCard] Error al importar datos:", err);
      setError(
        err instanceof ApiError || err instanceof TimeoutError
          ? err.message
          : "No pudimos importar los datos de tu empresa. Inténtalo nuevamente o complétalos a mano.",
      );
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
                  Marcamos sus regiones y rubros, y en el siguiente paso verás palabras clave
                  sugeridas.
                </p>
              </>
            ) : (
              <>
                <h3 id="company-import-title" className="text-sm font-bold text-text-strong">
                  Importa los datos de tu empresa
                </h3>
                <p className="text-sm text-text-muted">
                  Con el RUT <span className="font-mono text-text-body">{rut}</span> buscamos tus
                  actividades económicas en el SII para sugerirte regiones, rubros y palabras
                  clave. Podrás revisarlos antes de guardar.
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

      {error && (
        <div
          role="alert"
          className="mt-3 rounded-md border border-danger/20 bg-danger-soft/30 p-3 text-sm font-medium text-danger"
        >
          {error}
        </div>
      )}
    </section>
  );
}
