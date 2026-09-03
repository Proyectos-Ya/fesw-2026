import Image from "next/image";
import Link from "next/link";
import { MatchMeter } from "@/features/shared/components/MatchMeter";

export function AuthBrandPanel() {
  return (
    <div className="relative overflow-hidden bg-teal-600 p-12 flex flex-col min-h-full">
      {/* Texture circles */}
      <div className="absolute -right-24 -top-24 w-80 h-80 rounded-full bg-teal-500 opacity-45" />
      <div className="absolute right-16 -bottom-28 w-64 h-64 rounded-full bg-teal-700 opacity-50" />

      <Link href="/" className="relative z-10 w-fit">
        <Image
          src="/logo-color-dark.svg"
          alt="Chiripa"
          width={160}
          height={40}
          priority
        />
      </Link>

      <div className="relative z-10 mt-auto">
        <h2 className="text-white font-display text-6xl font-extrabold leading-[1.05] tracking-tight mb-4 max-w-md">
          Postula a la licitación <span className="text-coral-300 italic">correcta</span>, hoy.
        </h2>
        <p className="text-teal-100 text-lg mb-8 max-w-sm">
          Tus oportunidades de Compra Ágil, filtradas por IA y ordenadas por compatibilidad.
        </p>

        {/* Floating match card */}
        <div className="max-w-xs bg-white rounded-xl p-4 flex gap-4 items-center shadow-lg border border-teal-500/10">
          <MatchMeter value={94} size="md" />
          <div className="flex-1 min-w-0">
            <span className="inline-block bg-primary-soft text-primary text-[10px] font-bold uppercase tracking-caps px-2 py-0.5 rounded-full mb-1">
              Nuevo match
            </span>
            <div className="font-display font-semibold text-sm text-text-strong truncate">
              Aseo y mantención municipal
            </div>
            <div className="text-xs text-text-muted">Municipalidad de Ñuñoa</div>
          </div>
        </div>
      </div>
    </div>
  );
}
