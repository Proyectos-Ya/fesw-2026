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
 * Ágil en Mercado Público. Los pasos siguen el orden de ese formulario (guía
 * del proveedor de Compra Ágil, paso 2). `tenderCode` es `null` mientras no se
 * carga la ficha, y entonces tampoco está el cotizador de esta página.
 */
export function NextSteps({ view, tenderCode }: NextStepsProps) {
  const documentos = view.content?.required_documents.paragraphs ?? [];
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
          Ingresa el valor unitario neto de cada ítem, con el despacho incluido, y elige el
          tipo de impuesto: exento, IVA, honorario o zona franca.
          {tenderCode && (
            <>
              {" "}
              Puedes calcularlo en el{" "}
              <a href="#cotizacion" className="font-semibold text-primary underline">
                cotizador
              </a>{" "}
              de esta página.
            </>
          )}
        </li>
        {documentos.length > 0 && <li>Adjunta los documentos necesarios.</li>}
        {tecnico && (
          <li>
            Descarga el documento técnico en Word, revísalo y súbelo como adjunto. El
            formulario acepta archivos de hasta 20 MB.
          </li>
        )}
        <li>
          Copia el nombre de la oferta y el detalle de la cotización con los botones
          &quot;Copiar&quot;. Completa antes lo resaltado en amarillo.
        </li>
        <li>Indica la fecha de vigencia de tu oferta.</li>
        <li>
          Al enviar, acepta la Declaración Jurada de Habilidad en la ventana que muestra la
          plataforma. No se adjunta.
        </li>
      </ol>
    </section>
  );
}
