import Link from "next/link";
import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { Icon } from "@/features/shared/components/Icon";
import { MatchMeter } from "@/features/shared/components/MatchMeter";
import type { MatchingResult, Tender } from "../tenderTypes";
import {
  daysUntilClosing,
  formatCLP,
  formatClosingDate,
  normalizeScore,
  type ClosingTone,
} from "../utils/format";

interface TenderCardProps {
  match?: MatchingResult;
  tender?: Tender;
  isSaved?: boolean;
  onToggleSave?: (tenderId: string) => void;
}

const DASHBOARD_THRESHOLDS = { high: 70, mid: 40 };
const DASHBOARD_COLORS = {
  high: "var(--green-500)",
  mid: "var(--amber-500)",
  low: "var(--red-500)",
};

function closingBadgeTone(tone: ClosingTone): BadgeTone {
  switch (tone) {
    case "danger":
      return "danger";
    case "warning":
      return "warning";
    case "expired":
      return "neutral";
    default:
      return "neutral";
  }
}

function ScoreLabel({ score }: { score: number }) {
  if (score >= 70) return "Alta compatibilidad";
  if (score >= 40) return "Compatibilidad media";
  return "Baja compatibilidad";
}

export function TenderCard({ match, tender: rawTender, isSaved, onToggleSave }: TenderCardProps) {
  const tender: Tender | null = rawTender ?? match?.tender ?? null;
  if (!tender) return null;

  // Solo calcula el score si viene un objeto match definido
  const score = match ? normalizeScore(match.final_score) : null;
  const closing = daysUntilClosing(tender.closing_at);
  const buyer = tender.buyer_name ?? "Organismo no especificado";
  const savedState = isSaved ?? tender.is_saved ?? false;

  const handleSaveClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onToggleSave?.(tender.id);
  };

  return (
    <Link
      href={`/matches/${tender.id}`}
      className="group flex gap-5 rounded-lg border border-border-subtle bg-surface-card p-5 shadow-xs transition-all hover:border-primary hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      aria-label={`Ver detalle de ${tender.name}`}
    >
      {/* Medidor de compatibilidad: solo visible si hay match con score */}
      {score !== null && (
        <div className="flex-none">
          <MatchMeter
            value={score}
            size="lg"
            thresholds={DASHBOARD_THRESHOLDS}
            colors={DASHBOARD_COLORS}
          />
          <div className="mt-2 text-center text-[10px] font-bold uppercase tracking-caps text-text-subtle">
            <ScoreLabel score={score} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge tone="teal">Compra Ágil</Badge>
          <Badge tone={closingBadgeTone(closing.tone)} dot={closing.tone === "danger"}>
            {closing.label}
          </Badge>
          <span className="font-mono text-xs text-text-subtle">ID {tender.code}</span>

          <div className="flex-1" />

          {onToggleSave && (
            <button
              type="button"
              onClick={handleSaveClick}
              aria-label={savedState ? "Quitar de licitaciones guardadas" : "Guardar licitación"}
              title={savedState ? "Quitar de guardadas" : "Guardar licitación"}
              className={`inline-flex size-9 items-center justify-center rounded-full transition-all duration-200 cursor-pointer ${
                savedState
                  ? "bg-primary-soft text-primary hover:bg-teal-100 hover:scale-105 active:scale-95"
                  : "text-text-subtle hover:bg-surface-hover hover:text-primary hover:scale-105 active:scale-95"
              } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40`}
            >
              <Icon
                name={savedState ? "bookmark-check" : "bookmark"}
                size={19}
                color={savedState ? "var(--primary)" : "currentColor"}
              />
            </button>
          )}
        </div>

        <h3 className="font-display text-xl font-semibold leading-tight tracking-tight text-text-strong">
          {tender.name}
        </h3>

        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Icon name="building-2" size={15} color="var(--text-subtle)" />
            <span className="truncate">{buyer}</span>
          </span>
          {tender.region && (
            <>
              <span className="text-border-strong">·</span>
              <span className="inline-flex items-center gap-1.5">
                <Icon name="map-pin" size={15} color="var(--text-subtle)" />
                <span>{tender.region}</span>
              </span>
            </>
          )}
          <span className="text-border-strong">·</span>
          <span className="inline-flex items-center gap-1.5">
            <Icon name="clock" size={15} color="var(--text-subtle)" />
            <span>Cierra {formatClosingDate(tender.closing_at)}</span>
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-4">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-caps text-text-subtle">
              Monto estimado
            </div>
            <div className="font-mono text-lg font-semibold text-text-strong">
              {formatCLP(tender.available_amount_clp)}
            </div>
          </div>
          <div className="flex-1" />
          <span className="inline-flex items-center gap-2 rounded-md bg-primary-soft px-4 py-2 text-sm font-semibold text-primary transition-colors group-hover:bg-teal-100">
            Ver detalle
            <Icon name="arrow-right" size={16} />
          </span>
        </div>
      </div>
    </Link>
  );
}