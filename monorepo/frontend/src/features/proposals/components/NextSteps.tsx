import Link from "next/link";
import { compraAgilFichaUrl } from "@/features/matches/utils/links";
import { Icon } from "@/features/shared/components/Icon";
import type { ProposalView } from "../types";

interface NextStepsProps {
  view: ProposalView;
  tenderCode: string | null;
}

/**
 * Qué hacer con el borrador listo: Chiripa no postula por la empresa, así que
 * el último paso es llevar el texto y los archivos al formulario de la Compra
 * Ágil en Mercado Público.
 */
export function NextSteps({ view, tenderCode }: NextStepsProps) {
  const documentos = view.content?.required_documents.paragraphs ?? [];
  const pideCotizacion = documentos.some((d) => /cotizaci[oó]n/i.test(d.text));
  const tecnico = view.content?.technical_document ?? null;

  return (
    <section
      aria-labelledby="proximos-pasos"
      className="mb-6 rounded-lg border border-primary/20 bg-teal-50/40 p-5"
    >
      <h2 id="proximos-pasos" className="mb-3 text-sm font-bold text-text-strong">
        Próximos pasos para postular
      </h2>
      <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm text-text-body">
        <li>
          Abre la Compra Ágil en Mercado Público
          {tenderCode && (
            <>
              {": "}
              <a
                href={compraAgilFichaUrl(tenderCode)}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-semibold text-primary underline"
              >
                {tenderCode}
                <Icon name="external-link" size={13} />
              </a>
            </>
          )}
          .
        </li>
        <li>
          Copia el nombre y la descripción de la oferta al formulario con los botones
          &quot;Copiar&quot;. Completa antes lo resaltado en amarillo.
        </li>
        {documentos.length > 0 && (
          <li>
            Adjunta los documentos necesarios.
            {pideCotizacion && (
              <>
                {" "}
                Para la cotización puedes usar el{" "}
                <Link
                  href={`/matches/${view.tender_id}`}
                  className="font-semibold text-primary underline"
                >
                  cotizador de la licitación
                </Link>
                .
              </>
            )}
          </li>
        )}
        {tecnico && (
          <li>Descarga el documento técnico en Word, revísalo y súbelo como adjunto.</li>
        )}
      </ol>
    </section>
  );
}
